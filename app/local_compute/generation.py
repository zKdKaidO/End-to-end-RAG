"""Explicit local/user-funded generation routing with canonical Block 6 finalization."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from time import perf_counter
from typing import Any, Callable, Protocol
from urllib.parse import quote, urlparse
from uuid import UUID

import httpx
from starlette.concurrency import run_in_threadpool

from app.context.service import ContextBuilderService
from app.core.logging import get_logger
from app.generation.client import LLMResult
from app.generation.exceptions import GenerationDependencyError, GenerationTimeoutError
from app.generation.finalization import INSUFFICIENT_EVIDENCE_MESSAGE, finalize_generation_result
from app.generation.ollama import OllamaAdapter
from app.generation.profile import GenerationProfile, get_generation_profile
from app.generation.prompting import assemble_messages
from app.generation.schemas import AnswerabilityStatus, AnswerabilityValidation, CitationValidation, GenerationResult, GenerationStatus, Usage
from app.generation.tokenizers import ContextTokenCounter, PromptTokenCounter

from .context_adapter import build_local_context
from .errors import LocalComputeError, LocalComputeErrorCode
from .retrieval import LocalRetrievalStore


logger = get_logger(__name__)


def local_generation_profile(settings) -> GenerationProfile:
    """Construct the desktop generation contract from local settings only."""
    profile = GenerationProfile(
        provider="ollama",
        model_id=settings.generation_model_id,
        tokenizer_provider=settings.generation_tokenizer_provider,
        tokenizer_id=settings.generation_tokenizer_id,
        model_context_limit=settings.generation_model_context_limit,
        context_budget_tokens=settings.generation_context_budget_tokens,
        max_output_tokens=settings.generation_max_output_tokens,
        prompt_token_safety_margin=(
            settings.generation_prompt_token_safety_margin
        ),
        thinking=settings.generation_thinking,
        temperature=settings.generation_temperature,
        top_p=settings.generation_top_p,
        top_k=settings.generation_top_k,
        prompt_version=settings.generation_prompt_version,
        request_timeout_seconds=settings.generation_request_timeout_seconds,
    )
    profile.validate()
    return profile


class GenerationProviderType(str, Enum):
    LOCAL = "LOCAL"
    USER_CLOUD = "USER_CLOUD"
    PLATFORM_CLOUD = "PLATFORM_CLOUD"


class GenerationRoutingPolicy(str, Enum):
    LOCAL_ONLY = "LOCAL_ONLY"
    USER_CLOUD_ONLY = "USER_CLOUD_ONLY"
    PREFER_LOCAL = "PREFER_LOCAL"
    PREFER_USER_CLOUD = "PREFER_USER_CLOUD"


class GenerationProviderState(str, Enum):
    READY = "READY"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    MODEL_LOADING = "MODEL_LOADING"
    DEGRADED = "DEGRADED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    CREDENTIAL_UNAVAILABLE = "CREDENTIAL_UNAVAILABLE"
    UNREACHABLE = "UNREACHABLE"
    AUTH_FAILED = "AUTH_FAILED"
    RATE_LIMITED = "RATE_LIMITED"


# D1 import compatibility.
LocalGenerationState = GenerationProviderState


@dataclass(frozen=True)
class LocalGenerationAvailability:
    state: GenerationProviderState
    provider_type: GenerationProviderType
    model_id: str | None
    provider_config_id: str | None = None
    error_code: LocalComputeErrorCode | None = None


@dataclass(frozen=True)
class UserCloudProviderConfig:
    """Secret-free stable configuration for a user-owned reference transport."""

    provider_config_id: str
    endpoint: str
    model_id: str
    credential_ref: str
    transport: str = "OPENAI_COMPATIBLE"
    enabled: bool = True

    def validate(self, *, development_mode: bool) -> None:
        try:
            UUID(self.provider_config_id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST, "provider_config_id must be a UUID.") from exc
        if self.transport != "OPENAI_COMPATIBLE" or not self.model_id.strip() or not self.credential_ref.strip():
            raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST, "Invalid user-cloud provider configuration.")
        parsed = urlparse(self.endpoint)
        host = (parsed.hostname or "").lower()
        loopback_hosts = {"127.0.0.1", "::1", "localhost"}
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST, "Unsafe user-cloud endpoint.")
        if parsed.scheme == "https" and host:
            return
        if development_mode and parsed.scheme == "http" and host in loopback_hosts:
            return
        raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST, "User-cloud endpoints require HTTPS.")

    def metadata(self) -> dict[str, str | bool]:
        """Endpoint and credential reference are deliberately never serialized."""
        return {
            "provider_type": GenerationProviderType.USER_CLOUD.value,
            "provider_config_id": self.provider_config_id,
            "transport": self.transport,
            "model_id": self.model_id,
            "enabled": self.enabled,
            "privacy_boundary": "USER_CLOUD_EXTERNAL",
        }


class UserCloudCredentialStore(Protocol):
    secure: bool
    def get(self, credential_ref: str) -> str | None: ...


class UnavailableUserCloudCredentialStore:
    """Production default until an OS-protected secret backend exists."""
    secure = False
    def get(self, credential_ref: str) -> str | None:
        return None


class InMemoryUserCloudCredentialStore:
    """Development/test-only memory store; it has no persistence or serialization path."""
    secure = True

    def __init__(self, values: dict[str, str] | None = None) -> None:
        self._values = dict(values or {})

    def set(self, credential_ref: str, secret: str) -> None:
        if not credential_ref or not isinstance(secret, str) or not secret:
            raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST, "Invalid credential reference.")
        self._values[credential_ref] = secret

    def get(self, credential_ref: str) -> str | None:
        return self._values.get(credential_ref)


class _OllamaClient(Protocol):
    async def health(self, profile: GenerationProfile) -> None: ...
    async def generate(self, messages: list[dict[str, Any]], profile: GenerationProfile) -> LLMResult: ...
    async def close(self) -> None: ...


class _UserCloudTransport(Protocol):
    async def health(self, model_id: str, secret: str) -> None: ...
    async def generate(self, messages: list[dict[str, Any]], profile: GenerationProfile, model_id: str, secret: str) -> LLMResult: ...
    async def close(self) -> None: ...


class OpenAICompatibleTransport:
    """Reference wire adapter; only internal trusted configuration sets the endpoint."""

    def __init__(self, endpoint: str, timeout_seconds: float) -> None:
        self._client = httpx.AsyncClient(base_url=endpoint.rstrip("/") + "/", timeout=httpx.Timeout(timeout_seconds))

    @staticmethod
    def _headers(secret: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {secret}"}

    @staticmethod
    def _raise_sanitized(response: httpx.Response) -> None:
        if response.status_code in {401, 403}:
            raise LocalComputeError(LocalComputeErrorCode.USER_CLOUD_AUTH_FAILED)
        if response.status_code == 429:
            raise LocalComputeError(LocalComputeErrorCode.USER_CLOUD_RATE_LIMITED)
        if response.status_code == 404:
            raise LocalComputeError(LocalComputeErrorCode.USER_CLOUD_MODEL_UNAVAILABLE)
        raise LocalComputeError(LocalComputeErrorCode.USER_CLOUD_UNREACHABLE)

    async def health(self, model_id: str, secret: str) -> None:
        try:
            response = await self._client.get(f"models/{quote(model_id, safe='')}", headers=self._headers(secret))
            if response.status_code >= 400:
                self._raise_sanitized(response)
        except LocalComputeError:
            raise
        except httpx.TimeoutException as exc:
            raise LocalComputeError(LocalComputeErrorCode.GENERATION_TIMEOUT) from exc
        except httpx.HTTPError as exc:
            raise LocalComputeError(LocalComputeErrorCode.USER_CLOUD_UNREACHABLE) from exc

    async def generate(self, messages: list[dict[str, Any]], profile: GenerationProfile, model_id: str, secret: str) -> LLMResult:
        payload = {"model": model_id, "messages": messages, "temperature": profile.temperature, "top_p": profile.top_p, "max_tokens": profile.max_output_tokens, "stream": False}
        try:
            response = await self._client.post("chat/completions", json=payload, headers=self._headers(secret))
            if response.status_code >= 400:
                self._raise_sanitized(response)
            data = response.json()
        except LocalComputeError:
            raise
        except httpx.TimeoutException as exc:
            raise LocalComputeError(LocalComputeErrorCode.GENERATION_TIMEOUT) from exc
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise LocalComputeError(LocalComputeErrorCode.USER_CLOUD_UNREACHABLE) from exc
        try:
            choice = data["choices"][0]
            text = choice["message"]["content"]
            if not isinstance(text, str):
                raise TypeError
            raw_usage = data.get("usage") or {}
            usage = Usage(input_tokens=raw_usage.get("prompt_tokens"), output_tokens=raw_usage.get("completion_tokens"), total_tokens=raw_usage.get("total_tokens")) if raw_usage else None
            return LLMResult(text=text, finish_reason=choice.get("finish_reason"), usage=usage)
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise LocalComputeError(LocalComputeErrorCode.INVALID_GENERATION_RESPONSE) from exc

    async def close(self) -> None:
        await self._client.aclose()


class LocalGenerationProvider:
    """User-device provider; it accepts local Ollama endpoints only."""
    provider_type = GenerationProviderType.LOCAL

    def __init__(self, profile: GenerationProfile, endpoint: str, *, development_mode: bool = False, client: _OllamaClient | None = None) -> None:
        self.profile = profile
        self.endpoint = self._validated_local_endpoint(endpoint, development_mode)
        self._client = client or OllamaAdapter(endpoint, profile.request_timeout_seconds)

    @staticmethod
    def _validated_local_endpoint(endpoint: str, development_mode: bool) -> str:
        parsed = urlparse(endpoint)
        permitted = {"127.0.0.1", "::1"}
        if development_mode:
            permitted.add("host.docker.internal")
        if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").lower() not in permitted:
            raise LocalComputeError(LocalComputeErrorCode.GENERATION_UNAVAILABLE, "Configured local generation endpoint is not local.")
        return endpoint.rstrip("/")

    async def availability(self) -> LocalGenerationAvailability:
        try:
            await self._client.health(self.profile)
            return LocalGenerationAvailability(GenerationProviderState.READY, self.provider_type, self.profile.model_id)
        except GenerationTimeoutError:
            return LocalGenerationAvailability(GenerationProviderState.DEGRADED, self.provider_type, self.profile.model_id)
        except GenerationDependencyError as exc:
            state = GenerationProviderState.MODEL_UNAVAILABLE if exc.error_code == "MODEL_UNAVAILABLE" else GenerationProviderState.DEGRADED
            return LocalGenerationAvailability(state, self.provider_type, self.profile.model_id)

    def model_info(self) -> dict[str, str]:
        return {"provider": self.provider_type.value, "model_id": self.profile.model_id}

    async def generate(self, messages: list[dict[str, Any]]) -> LLMResult:
        availability = await self.availability()
        if availability.state != GenerationProviderState.READY:
            raise LocalComputeError(LocalComputeErrorCode.MODEL_UNAVAILABLE if availability.state == GenerationProviderState.MODEL_UNAVAILABLE else LocalComputeErrorCode.GENERATION_UNAVAILABLE)
        try:
            result = await self._client.generate(messages, self.profile)
        except GenerationTimeoutError as exc:
            raise LocalComputeError(LocalComputeErrorCode.GENERATION_TIMEOUT) from exc
        except GenerationDependencyError as exc:
            raise LocalComputeError(LocalComputeErrorCode.MODEL_UNAVAILABLE if exc.error_code == "MODEL_UNAVAILABLE" else LocalComputeErrorCode.GENERATION_UNAVAILABLE) from exc
        if not isinstance(result.text, str):
            raise LocalComputeError(LocalComputeErrorCode.INVALID_GENERATION_RESPONSE)
        return result

    async def cancel(self) -> bool:
        return False

    async def close(self) -> None:
        await self._client.close()


class UserCloudGenerationProvider:
    """User-owned external generation; no platform credential or relay exists."""
    provider_type = GenerationProviderType.USER_CLOUD

    def __init__(self, config: UserCloudProviderConfig, profile: GenerationProfile, credential_store: UserCloudCredentialStore, *, development_mode: bool, transport: _UserCloudTransport | None = None) -> None:
        config.validate(development_mode=development_mode)
        self.config, self.profile, self.credential_store = config, profile, credential_store
        self._transport = transport or OpenAICompatibleTransport(config.endpoint, profile.request_timeout_seconds)

    def _credential(self) -> str:
        secret = self.credential_store.get(self.config.credential_ref)
        if not secret:
            raise LocalComputeError(LocalComputeErrorCode.CREDENTIAL_UNAVAILABLE)
        return secret

    async def availability(self) -> LocalGenerationAvailability:
        if not self.config.enabled:
            return LocalGenerationAvailability(GenerationProviderState.NOT_CONFIGURED, self.provider_type, self.config.model_id, self.config.provider_config_id)
        try:
            await self._transport.health(self.config.model_id, self._credential())
            return LocalGenerationAvailability(GenerationProviderState.READY, self.provider_type, self.config.model_id, self.config.provider_config_id)
        except LocalComputeError as exc:
            states = {LocalComputeErrorCode.CREDENTIAL_UNAVAILABLE: GenerationProviderState.CREDENTIAL_UNAVAILABLE, LocalComputeErrorCode.USER_CLOUD_AUTH_FAILED: GenerationProviderState.AUTH_FAILED, LocalComputeErrorCode.USER_CLOUD_RATE_LIMITED: GenerationProviderState.RATE_LIMITED, LocalComputeErrorCode.USER_CLOUD_MODEL_UNAVAILABLE: GenerationProviderState.MODEL_UNAVAILABLE, LocalComputeErrorCode.GENERATION_TIMEOUT: GenerationProviderState.DEGRADED}
            return LocalGenerationAvailability(states.get(exc.code, GenerationProviderState.UNREACHABLE), self.provider_type, self.config.model_id, self.config.provider_config_id, exc.code)

    def model_info(self) -> dict[str, str | bool]:
        return self.config.metadata()

    async def generate(self, messages: list[dict[str, Any]]) -> LLMResult:
        availability = await self.availability()
        if availability.state != GenerationProviderState.READY:
            raise LocalComputeError(availability.error_code or LocalComputeErrorCode.USER_CLOUD_UNREACHABLE)
        result = await self._transport.generate(messages, self.profile, self.config.model_id, self._credential())
        if not isinstance(result.text, str):
            raise LocalComputeError(LocalComputeErrorCode.INVALID_GENERATION_RESPONSE)
        return result

    async def cancel(self) -> bool:
        return False

    async def close(self) -> None:
        await self._transport.close()


class UserCloudProviderRegistry:
    """Internal-only config boundary; no protocol route accepts provider endpoints."""
    def __init__(self, credential_store: UserCloudCredentialStore, *, development_mode: bool, provider_factory: Callable[[UserCloudProviderConfig], UserCloudGenerationProvider] | None = None, profile: GenerationProfile | None = None) -> None:
        self.credential_store, self.development_mode = credential_store, development_mode
        self.profile = profile or get_generation_profile()
        self._providers: dict[str, UserCloudGenerationProvider] = {}
        self._provider_factory = provider_factory

    def configure(self, config: UserCloudProviderConfig) -> None:
        if not self.development_mode and (
            not self.credential_store.secure or isinstance(self.credential_store, InMemoryUserCloudCredentialStore)
        ):
            raise LocalComputeError(LocalComputeErrorCode.CREDENTIAL_STORE_UNAVAILABLE)
        config.validate(development_mode=self.development_mode)
        self._providers[config.provider_config_id] = self._provider_factory(config) if self._provider_factory else UserCloudGenerationProvider(config, self.profile, self.credential_store, development_mode=self.development_mode)

    def provider(self, config_id: str | None) -> UserCloudGenerationProvider:
        if not config_id or config_id not in self._providers:
            raise LocalComputeError(LocalComputeErrorCode.USER_CLOUD_NOT_CONFIGURED)
        return self._providers[config_id]

    async def availability(self, config_id: str | None) -> LocalGenerationAvailability:
        if not config_id:
            return LocalGenerationAvailability(GenerationProviderState.NOT_CONFIGURED, GenerationProviderType.USER_CLOUD, None)
        return await self.provider(config_id).availability()


@dataclass(frozen=True)
class GenerationRoutingRequest:
    policy: GenerationRoutingPolicy = GenerationRoutingPolicy.LOCAL_ONLY
    provider_config_id: str | None = None
    allow_user_cloud_fallback: bool = False
    allow_local_fallback: bool = False

    @classmethod
    def from_values(cls, *, policy: str | None = None, provider_config_id: str | None = None, allow_user_cloud_fallback: bool = False, allow_local_fallback: bool = False) -> "GenerationRoutingRequest":
        try:
            parsed = GenerationRoutingPolicy(policy or GenerationRoutingPolicy.LOCAL_ONLY.value)
        except ValueError as exc:
            raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST, "Unknown generation routing policy.") from exc
        if not isinstance(allow_user_cloud_fallback, bool) or not isinstance(allow_local_fallback, bool):
            raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST, "Routing fallback permissions must be boolean.")
        return cls(parsed, provider_config_id, allow_user_cloud_fallback, allow_local_fallback)


@dataclass(frozen=True)
class GenerationRouteDecision:
    provider: LocalGenerationProvider | UserCloudGenerationProvider
    policy: GenerationRoutingPolicy
    fallback_occurred: bool

    @property
    def provider_type(self) -> GenerationProviderType:
        return self.provider.provider_type

    @property
    def model_id(self) -> str:
        return self.provider.profile.model_id if self.provider_type == GenerationProviderType.LOCAL else self.provider.config.model_id

    @property
    def provider_config_id(self) -> str | None:
        return None if self.provider_type == GenerationProviderType.LOCAL else self.provider.config.provider_config_id

    def metadata(self) -> dict[str, Any]:
        return {"policy": self.policy.value, "selected_provider_type": self.provider_type.value, "provider_config_id": self.provider_config_id, "fallback_occurred": self.fallback_occurred, "privacy_boundary": "LOCAL_DEVICE" if self.provider_type == GenerationProviderType.LOCAL else "USER_CLOUD_EXTERNAL"}


class GenerationRouter:
    """Explicit policy router. Platform cloud has no executable implementation."""
    def __init__(self, local_provider: LocalGenerationProvider, user_cloud_registry: UserCloudProviderRegistry | None = None) -> None:
        self.local_provider = local_provider
        self.user_cloud_registry = user_cloud_registry or UserCloudProviderRegistry(UnavailableUserCloudCredentialStore(), development_mode=False, profile=local_provider.profile)

    async def availability(self) -> LocalGenerationAvailability:
        return await self.local_provider.availability()

    async def capability_report(self) -> dict[str, Any]:
        local, user_cloud = await self.local_provider.availability(), await self.user_cloud_registry.availability(None)
        return {"default_policy": GenerationRoutingPolicy.LOCAL_ONLY.value, "local": {"state": local.state.value, "model_id": local.model_id}, "user_cloud": {"state": user_cloud.state.value}, "platform_cloud": "DISABLED"}

    async def _local_ready(self) -> LocalGenerationProvider | None:
        return self.local_provider if (await self.local_provider.availability()).state == GenerationProviderState.READY else None

    async def _user_cloud_ready(self, config_id: str | None) -> UserCloudGenerationProvider | None:
        provider = self.user_cloud_registry.provider(config_id)
        return provider if (await provider.availability()).state == GenerationProviderState.READY else None

    async def resolve(self, request: GenerationRoutingRequest) -> GenerationRouteDecision:
        if request.policy == GenerationRoutingPolicy.LOCAL_ONLY:
            if local := await self._local_ready(): return GenerationRouteDecision(local, request.policy, False)
            raise LocalComputeError(LocalComputeErrorCode.GENERATION_UNAVAILABLE)
        if request.policy == GenerationRoutingPolicy.USER_CLOUD_ONLY:
            if cloud := await self._user_cloud_ready(request.provider_config_id): return GenerationRouteDecision(cloud, request.policy, False)
            raise LocalComputeError(LocalComputeErrorCode.USER_CLOUD_UNREACHABLE)
        if request.policy == GenerationRoutingPolicy.PREFER_LOCAL:
            if local := await self._local_ready(): return GenerationRouteDecision(local, request.policy, False)
            if not request.allow_user_cloud_fallback: raise LocalComputeError(LocalComputeErrorCode.GENERATION_UNAVAILABLE)
            if cloud := await self._user_cloud_ready(request.provider_config_id): return GenerationRouteDecision(cloud, request.policy, True)
            raise LocalComputeError(LocalComputeErrorCode.USER_CLOUD_UNREACHABLE)
        if request.policy == GenerationRoutingPolicy.PREFER_USER_CLOUD:
            if cloud := await self._user_cloud_ready(request.provider_config_id): return GenerationRouteDecision(cloud, request.policy, False)
            if not request.allow_local_fallback: raise LocalComputeError(LocalComputeErrorCode.USER_CLOUD_UNREACHABLE)
            if local := await self._local_ready(): return GenerationRouteDecision(local, request.policy, True)
            raise LocalComputeError(LocalComputeErrorCode.GENERATION_UNAVAILABLE)
        raise LocalComputeError(LocalComputeErrorCode.PROVIDER_NOT_SUPPORTED)

    def provider_for(self, provider_type: GenerationProviderType = GenerationProviderType.LOCAL) -> LocalGenerationProvider:
        """D1 compatibility helper; it never triggers cloud selection."""
        if provider_type == GenerationProviderType.PLATFORM_CLOUD:
            raise LocalComputeError(LocalComputeErrorCode.PLATFORM_CLOUD_DISABLED)
        if provider_type != GenerationProviderType.LOCAL:
            raise LocalComputeError(LocalComputeErrorCode.CAPABILITY_UNAVAILABLE)
        return self.local_provider


@dataclass(frozen=True)
class LocalAnswerResponse:
    provider: GenerationProviderType
    model_id: str
    result: GenerationResult
    hierarchy: dict[str, Any]
    timings: dict[str, float | None]
    provider_config_id: str | None = None
    routing: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"provider": self.provider.value, "provider_type": self.provider.value, "provider_config_id": self.provider_config_id, "model_id": self.model_id, "result": self.result.model_dump(mode="json"), "hierarchy": self.hierarchy, "timings": self.timings, "routing": self.routing or {"policy": GenerationRoutingPolicy.LOCAL_ONLY.value, "selected_provider_type": self.provider.value, "fallback_occurred": False, "privacy_boundary": "LOCAL_DEVICE"}}


class LocalAnswerService:
    """Canonical Blocks 4–6 with explicit, never-platform-paid routing."""
    def __init__(self, settings, catalog, router: GenerationRouter, *, profile: GenerationProfile | None = None, retrieval_store: LocalRetrievalStore | None = None, context_builder: ContextBuilderService | None = None, prompt_counter: PromptTokenCounter | None = None) -> None:
        self.settings, self.profile, self.router = settings, profile or get_generation_profile(), router
        self.profile.validate()
        self.retrieval_store = retrieval_store or LocalRetrievalStore(settings, catalog)
        self.context_builder = context_builder or ContextBuilderService(ContextTokenCounter(self.profile.tokenizer_provider, self.profile.tokenizer_id))
        self.prompt_counter = prompt_counter or PromptTokenCounter(self.profile.tokenizer_provider, self.profile.tokenizer_id, thinking=self.profile.thinking)

    async def answer(self, *, request_id: str, query_text: str, document_ids: list[str] | None, routing: GenerationRoutingRequest | None = None) -> LocalAnswerResponse:
        query_text, routing = self._validate_request(query_text, document_ids), routing or GenerationRoutingRequest()
        started, retrieval_started = perf_counter(), perf_counter()
        local_results, hierarchy = await run_in_threadpool(self.retrieval_store.query_document_set_with_diagnostics, query_text, document_ids)
        retrieval_ms, context_started = (perf_counter() - retrieval_started) * 1000, perf_counter()
        package = await run_in_threadpool(build_local_context, request_id=request_id, query_text=query_text, local_results=local_results, context_budget_tokens=self.profile.context_budget_tokens, context_builder=self.context_builder)
        timings: dict[str, float | None] = {"retrieval_ms": round(retrieval_ms, 3), "context_build_ms": round((perf_counter() - context_started) * 1000, 3), "prompt_token_count": None, "generation_ms": None, "total_ms": None, "time_to_first_token_ms": None}
        if package.selected_count == 0:
            result = GenerationResult(request_id=request_id, status=GenerationStatus.INSUFFICIENT_EVIDENCE, answer_text=INSUFFICIENT_EVIDENCE_MESSAGE, citations=[], invalid_citations=[], citation_validation=CitationValidation.PASS, model_id=self.profile.model_id, prompt_version=self.profile.prompt_version, finish_reason=None, usage=None, answerability_status=AnswerabilityStatus.INSUFFICIENT_EVIDENCE, answerability_validation=AnswerabilityValidation.NOT_APPLICABLE)
            timings["total_ms"] = round((perf_counter() - started) * 1000, 3)
            return LocalAnswerResponse(GenerationProviderType.LOCAL, self.profile.model_id, result, hierarchy, timings)
        messages = assemble_messages(package, self.profile.prompt_version)
        prompt_tokens = self.prompt_counter.count_messages(messages)
        timings["prompt_token_count"] = float(prompt_tokens)
        if prompt_tokens + self.profile.max_output_tokens + self.profile.prompt_token_safety_margin > self.profile.model_context_limit:
            raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST, "The final prompt exceeds the configured model context limit.")
        decision, generation_started = await self.router.resolve(routing), perf_counter()
        provider_result = await decision.provider.generate(messages)
        timings["generation_ms"] = round((perf_counter() - generation_started) * 1000, 3)
        result = finalize_generation_result(request_id=request_id, package=package, profile=self.profile, provider_text=provider_result.text, finish_reason=provider_result.finish_reason, usage=provider_result.usage, model_id=decision.model_id)
        timings["total_ms"] = round((perf_counter() - started) * 1000, 3)
        logger.info("local_generation_completed", request_id=request_id, provider_type=decision.provider_type.value, provider_config_id=decision.provider_config_id, model_id=decision.model_id, routing_policy=routing.policy.value, fallback_occurred=decision.fallback_occurred, prompt_tokens=prompt_tokens, output_tokens=result.usage.output_tokens if result.usage else None, citation_count=len(result.citations), generation_status=result.status.value, total_ms=timings["total_ms"])
        return LocalAnswerResponse(decision.provider_type, decision.model_id, result, hierarchy, timings, decision.provider_config_id, decision.metadata())

    @staticmethod
    def _validate_request(query_text: str, document_ids: list[str] | None) -> str:
        if not isinstance(query_text, str) or not query_text.strip():
            raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST, "query_text must not be empty.")
        if document_ids is not None:
            if not isinstance(document_ids, list) or len(document_ids) > 100: raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST)
            try:
                if len({str(UUID(value)) for value in document_ids}) != len(document_ids): raise ValueError
            except (ValueError, TypeError, AttributeError) as exc:
                raise LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST) from exc
        return query_text.strip()
