"""Local-only provider routing and Block 6-compatible answer orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from time import perf_counter
from typing import Any, Protocol
from urllib.parse import urlparse
from uuid import UUID

from starlette.concurrency import run_in_threadpool

from app.context.service import ContextBuilderService
from app.core.logging import get_logger
from app.generation.client import LLMResult
from app.generation.exceptions import GenerationDependencyError, GenerationTimeoutError
from app.generation.finalization import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    finalize_generation_result,
)
from app.generation.ollama import OllamaAdapter
from app.generation.profile import GenerationProfile, get_generation_profile
from app.generation.prompting import assemble_messages
from app.generation.schemas import (
    AnswerabilityStatus,
    AnswerabilityValidation,
    CitationValidation,
    GenerationResult,
    GenerationStatus,
)
from app.generation.tokenizers import ContextTokenCounter, PromptTokenCounter

from .context_adapter import build_local_context
from .errors import LocalComputeError, LocalComputeErrorCode
from .retrieval import LocalRetrievalStore


logger = get_logger(__name__)


class GenerationProviderType(str, Enum):
    LOCAL = "LOCAL"
    USER_CLOUD = "USER_CLOUD"
    PLATFORM_CLOUD = "PLATFORM_CLOUD"


class LocalGenerationState(str, Enum):
    READY = "READY"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    MODEL_LOADING = "MODEL_LOADING"
    DEGRADED = "DEGRADED"
    NOT_SUPPORTED = "NOT_SUPPORTED"


@dataclass(frozen=True)
class LocalGenerationAvailability:
    state: LocalGenerationState
    provider_type: GenerationProviderType
    model_id: str


@dataclass(frozen=True)
class LocalAnswerResponse:
    provider: GenerationProviderType
    model_id: str
    result: GenerationResult
    hierarchy: dict[str, Any]
    timings: dict[str, float | None]

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider.value,
            "model_id": self.model_id,
            "result": self.result.model_dump(mode="json"),
            "hierarchy": self.hierarchy,
            "timings": self.timings,
        }


class _OllamaClient(Protocol):
    async def health(self, profile: GenerationProfile) -> None: ...

    async def generate(
        self, messages: list[dict[str, Any]], profile: GenerationProfile
    ) -> LLMResult: ...

    async def close(self) -> None: ...


class LocalGenerationProvider:
    """The only executable V1 provider; it accepts local Ollama only."""

    provider_type = GenerationProviderType.LOCAL

    def __init__(
        self,
        profile: GenerationProfile,
        endpoint: str,
        *,
        development_mode: bool = False,
        client: _OllamaClient | None = None,
    ) -> None:
        self.profile = profile
        self.endpoint = self._validated_local_endpoint(endpoint, development_mode)
        self._client = client or OllamaAdapter(endpoint, profile.request_timeout_seconds)

    @staticmethod
    def _validated_local_endpoint(endpoint: str, development_mode: bool) -> str:
        parsed = urlparse(endpoint)
        host = (parsed.hostname or "").lower()
        permitted = {"127.0.0.1", "::1"}
        # Docker Desktop's gateway is only allowed for this repository's
        # isolated development acceptance path; packaged Compute uses loopback.
        if development_mode:
            permitted.add("host.docker.internal")
        if parsed.scheme not in {"http", "https"} or host not in permitted:
            raise LocalComputeError(
                LocalComputeErrorCode.GENERATION_UNAVAILABLE,
                "Configured local generation endpoint is not local.",
            )
        return endpoint.rstrip("/")

    async def availability(self) -> LocalGenerationAvailability:
        try:
            await self._client.health(self.profile)
            return LocalGenerationAvailability(
                LocalGenerationState.READY,
                self.provider_type,
                self.profile.model_id,
            )
        except GenerationTimeoutError:
            return LocalGenerationAvailability(
                LocalGenerationState.DEGRADED,
                self.provider_type,
                self.profile.model_id,
            )
        except GenerationDependencyError as exc:
            state = (
                LocalGenerationState.MODEL_UNAVAILABLE
                if exc.error_code == "MODEL_UNAVAILABLE"
                else LocalGenerationState.DEGRADED
            )
            return LocalGenerationAvailability(state, self.provider_type, self.profile.model_id)

    def model_info(self) -> dict[str, str]:
        return {"provider": self.provider_type.value, "model_id": self.profile.model_id}

    async def generate(self, messages: list[dict[str, Any]]) -> LLMResult:
        availability = await self.availability()
        if availability.state != LocalGenerationState.READY:
            code = (
                LocalComputeErrorCode.MODEL_UNAVAILABLE
                if availability.state == LocalGenerationState.MODEL_UNAVAILABLE
                else LocalComputeErrorCode.GENERATION_UNAVAILABLE
            )
            raise LocalComputeError(code)
        try:
            result = await self._client.generate(messages, self.profile)
        except GenerationTimeoutError as exc:
            raise LocalComputeError(LocalComputeErrorCode.GENERATION_TIMEOUT) from exc
        except GenerationDependencyError as exc:
            code = (
                LocalComputeErrorCode.MODEL_UNAVAILABLE
                if exc.error_code == "MODEL_UNAVAILABLE"
                else LocalComputeErrorCode.GENERATION_UNAVAILABLE
            )
            raise LocalComputeError(code) from exc
        if not isinstance(result.text, str):
            raise LocalComputeError(LocalComputeErrorCode.INVALID_GENERATION_RESPONSE)
        return result

    async def cancel(self) -> bool:
        """Ollama's non-streaming request API has no safe per-request cancel."""

        return False

    async def close(self) -> None:
        await self._client.close()


class GenerationRouter:
    """Provider policy is explicit: local only in P2C.4D.1."""

    def __init__(self, local_provider: LocalGenerationProvider) -> None:
        self.local_provider = local_provider

    async def availability(self) -> LocalGenerationAvailability:
        return await self.local_provider.availability()

    def provider_for(self, provider_type: GenerationProviderType = GenerationProviderType.LOCAL) -> LocalGenerationProvider:
        if provider_type != GenerationProviderType.LOCAL:
            raise LocalComputeError(LocalComputeErrorCode.CAPABILITY_UNAVAILABLE)
        return self.local_provider


class LocalAnswerService:
    """Local Block 4–6 pipeline with no platform relay or fallback provider."""

    def __init__(
        self,
        settings,
        catalog,
        router: GenerationRouter,
        *,
        profile: GenerationProfile | None = None,
        retrieval_store: LocalRetrievalStore | None = None,
        context_builder: ContextBuilderService | None = None,
        prompt_counter: PromptTokenCounter | None = None,
    ) -> None:
        self.settings = settings
        self.profile = profile or get_generation_profile()
        self.profile.validate()
        self.router = router
        self.retrieval_store = retrieval_store or LocalRetrievalStore(settings, catalog)
        self.context_builder = context_builder or ContextBuilderService(
            ContextTokenCounter(self.profile.tokenizer_provider, self.profile.tokenizer_id)
        )
        self.prompt_counter = prompt_counter or PromptTokenCounter(
            self.profile.tokenizer_provider,
            self.profile.tokenizer_id,
            thinking=self.profile.thinking,
        )

    async def answer(
        self,
        *,
        request_id: str,
        query_text: str,
        document_ids: list[str] | None,
    ) -> LocalAnswerResponse:
        query_text = self._validate_request(query_text, document_ids)
        started = perf_counter()
        retrieval_started = perf_counter()
        local_results, hierarchy = await run_in_threadpool(
            self.retrieval_store.query_document_set_with_diagnostics,
            query_text,
            document_ids,
        )
        retrieval_ms = (perf_counter() - retrieval_started) * 1000

        context_started = perf_counter()
        package = await run_in_threadpool(
            build_local_context,
            request_id=request_id,
            query_text=query_text,
            local_results=local_results,
            context_budget_tokens=self.profile.context_budget_tokens,
            context_builder=self.context_builder,
        )
        context_ms = (perf_counter() - context_started) * 1000
        timings: dict[str, float | None] = {
            "retrieval_ms": round(retrieval_ms, 3),
            "context_build_ms": round(context_ms, 3),
            "prompt_token_count": None,
            "generation_ms": None,
            "total_ms": None,
            "time_to_first_token_ms": None,
        }
        if package.selected_count == 0:
            result = GenerationResult(
                request_id=request_id,
                status=GenerationStatus.INSUFFICIENT_EVIDENCE,
                answer_text=INSUFFICIENT_EVIDENCE_MESSAGE,
                citations=[],
                invalid_citations=[],
                citation_validation=CitationValidation.PASS,
                model_id=self.profile.model_id,
                prompt_version=self.profile.prompt_version,
                finish_reason=None,
                usage=None,
                answerability_status=AnswerabilityStatus.INSUFFICIENT_EVIDENCE,
                answerability_validation=AnswerabilityValidation.NOT_APPLICABLE,
            )
            timings["total_ms"] = round((perf_counter() - started) * 1000, 3)
            return LocalAnswerResponse(GenerationProviderType.LOCAL, self.profile.model_id, result, hierarchy, timings)

        messages = assemble_messages(package, self.profile.prompt_version)
        prompt_tokens = self.prompt_counter.count_messages(messages)
        timings["prompt_token_count"] = float(prompt_tokens)
        if prompt_tokens + self.profile.max_output_tokens + self.profile.prompt_token_safety_margin > self.profile.model_context_limit:
            raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST, "The final prompt exceeds the configured model context limit.")

        generation_started = perf_counter()
        provider = self.router.provider_for()
        provider_result = await provider.generate(messages)
        timings["generation_ms"] = round((perf_counter() - generation_started) * 1000, 3)
        result = finalize_generation_result(
            request_id=request_id,
            package=package,
            profile=self.profile,
            provider_text=provider_result.text,
            finish_reason=provider_result.finish_reason,
            usage=provider_result.usage,
        )
        timings["total_ms"] = round((perf_counter() - started) * 1000, 3)
        logger.info(
            "local_generation_completed",
            request_id=request_id,
            provider_type=GenerationProviderType.LOCAL.value,
            model_id=self.profile.model_id,
            prompt_tokens=prompt_tokens,
            output_tokens=result.usage.output_tokens if result.usage else None,
            citation_count=len(result.citations),
            generation_status=result.status.value,
            total_ms=timings["total_ms"],
        )
        return LocalAnswerResponse(GenerationProviderType.LOCAL, self.profile.model_id, result, hierarchy, timings)

    @staticmethod
    def _validate_request(query_text: str, document_ids: list[str] | None) -> str:
        if not isinstance(query_text, str) or not query_text.strip():
            raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST, "query_text must not be empty.")
        if document_ids is not None:
            if not isinstance(document_ids, list):
                raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST)
            if len(document_ids) > 100:
                raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST)
            try:
                if len({str(UUID(value)) for value in document_ids}) != len(document_ids):
                    raise ValueError
            except (ValueError, TypeError, AttributeError) as exc:
                raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST) from exc
        return query_text.strip()
