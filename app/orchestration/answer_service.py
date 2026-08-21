from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from functools import partial
from time import perf_counter

from starlette.concurrency import run_in_threadpool

from app.context.exceptions import ContextBuilderError, TokenCounterDependencyError
from app.context.schemas import ContextPackage
from app.context.service import ContextBuilderService
from app.core.logging import get_logger
from app.generation.citations import validate_and_map_citations
from app.generation.answerability import (
    StreamingMarkerFilter,
    parse_answerability,
    resolved_prefix,
    strip_internal_markers,
)
from app.generation.client import LLMClient
from app.generation.exceptions import (
    GenerationConfigurationError,
    GenerationDependencyError,
    GenerationError,
    GenerationValidationError,
)
from app.generation.profile import GenerationProfile
from app.generation.prompting import assemble_messages
from app.generation.schemas import (
    AnswerabilityStatus,
    AnswerabilityValidation,
    AnswerRequest,
    CitationValidation,
    GenerationResult,
    GenerationStatus,
)
from app.generation.tokenizers import ContextTokenCounter, PromptTokenCounter
from app.retrieval.exceptions import (
    RetrievalDependencyError,
    RetrievalError,
    RetrievalValidationError,
)
from app.retrieval.schemas import RetrievalRequest
from app.retrieval.service import RetrievalService, validate_request


logger = get_logger(__name__)
INSUFFICIENT_EVIDENCE_MESSAGE = "Bằng chứng được cung cấp không đủ để trả lời câu hỏi."


@dataclass
class PreparedAnswer:
    request_id: str
    package: ContextPackage
    messages: list[dict[str, str]]
    prompt_tokens: int
    early_result: GenerationResult | None = None
    timings: dict[str, float] = field(default_factory=dict)
    started: float = field(default_factory=perf_counter)


class AnswerService:
    def __init__(
        self,
        retrieval_service: RetrievalService,
        llm_client: LLMClient,
        profile: GenerationProfile,
        *,
        context_builder: ContextBuilderService | None = None,
        prompt_counter: PromptTokenCounter | None = None,
    ):
        try:
            profile.validate()
        except ValueError as exc:
            raise GenerationConfigurationError(
                "VALIDATE_REQUEST", "GENERATION_PROFILE_INVALID", "Generation profile is invalid"
            ) from exc
        self.retrieval_service = retrieval_service
        self.llm_client = llm_client
        self.profile = profile
        try:
            self.context_builder = context_builder or ContextBuilderService(
                ContextTokenCounter(profile.tokenizer_provider, profile.tokenizer_id)
            )
            self.prompt_counter = prompt_counter or PromptTokenCounter(
                profile.tokenizer_provider, profile.tokenizer_id, thinking=profile.thinking
            )
        except Exception as exc:
            raise GenerationConfigurationError(
                "VALIDATE_REQUEST", "GENERATION_PROFILE_INVALID", "Generation tokenizer is unavailable"
            ) from exc

    async def prepare(self, request_id: str, request: AnswerRequest) -> PreparedAnswer:
        started = perf_counter()
        query_text = request.query_text.strip()
        if not query_text:
            raise GenerationValidationError(
                "VALIDATE_REQUEST", "INVALID_QUERY", "query_text must not be empty or whitespace-only"
            )
        try:
            params = validate_request(
                RetrievalRequest(query_text=query_text, document_ids=request.document_ids)
            )
            stage_started = perf_counter()
            retrieved = await run_in_threadpool(self.retrieval_service.retrieve, params)
            retrieval_ms = (perf_counter() - stage_started) * 1000
        except RetrievalValidationError as exc:
            code = "QUERY_TOO_LONG" if exc.stage == "QUERY_EMBEDDING" else "INVALID_REQUEST"
            raise GenerationValidationError(f"RETRIEVAL.{exc.stage}", code, exc.message) from exc
        except RetrievalDependencyError as exc:
            raise GenerationDependencyError(
                f"RETRIEVAL.{exc.stage}", "RETRIEVAL_UNAVAILABLE", exc.message
            ) from exc
        except RetrievalError as exc:
            raise GenerationError(f"RETRIEVAL.{exc.stage}", "RETRIEVAL_ERROR", exc.message) from exc

        try:
            stage_started = perf_counter()
            package = await run_in_threadpool(
                partial(
                    self.context_builder.build,
                    request_id=request_id,
                    query_text=query_text,
                    retrieved_candidates=retrieved,
                    context_budget_tokens=self.profile.context_budget_tokens,
                )
            )
            context_build_ms = (perf_counter() - stage_started) * 1000
        except TokenCounterDependencyError as exc:
            raise GenerationDependencyError(
                f"CONTEXT_BUILDING.{exc.stage}", "TOKENIZER_UNAVAILABLE", exc.message
            ) from exc
        except ContextBuilderError as exc:
            raise GenerationError(f"CONTEXT_BUILDING.{exc.stage}", "CONTEXT_BUILD_ERROR", exc.message) from exc

        timings = {"retrieval_ms": retrieval_ms, "context_build_ms": context_build_ms}
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
            return PreparedAnswer(request_id, package, [], 0, result, timings, started)

        stage_started = perf_counter()
        messages = assemble_messages(package, self.profile.prompt_version)
        timings["prompt_build_ms"] = (perf_counter() - stage_started) * 1000
        try:
            stage_started = perf_counter()
            prompt_tokens = self.prompt_counter.count_messages(messages)
            timings["prompt_token_count_ms"] = (perf_counter() - stage_started) * 1000
        except Exception as exc:
            raise GenerationDependencyError(
                "PROMPT_TOKEN_COUNT", "TOKENIZER_UNAVAILABLE", "Prompt tokenizer is unavailable"
            ) from exc

        if (
            prompt_tokens
            + self.profile.max_output_tokens
            + self.profile.prompt_token_safety_margin
            > self.profile.model_context_limit
        ):
            raise GenerationValidationError(
                "PROMPT_BUDGET_GUARD",
                "QUERY_TOO_LONG",
                "The final prompt exceeds the configured model context limit",
            )
        logger.info(
            "answer_prepared",
            request_id=request_id,
            stage="PROMPT_BUDGET_GUARD",
            retrieved_count=len(retrieved),
            selected_evidence_count=package.selected_count,
            context_tokens=package.context_token_count,
            prompt_tokens=prompt_tokens,
            model_id=self.profile.model_id,
            prompt_version=self.profile.prompt_version,
            **{key: round(value, 3) for key, value in timings.items()},
        )
        return PreparedAnswer(request_id, package, messages, prompt_tokens, None, timings, started)

    def _finalize(self, prepared: PreparedAnswer, provider_text: str, finish_reason, usage) -> GenerationResult:
        parsed = parse_answerability(provider_text)
        if parsed.status == AnswerabilityStatus.INSUFFICIENT_EVIDENCE:
            result = GenerationResult(
                request_id=prepared.request_id,
                status=GenerationStatus.INSUFFICIENT_EVIDENCE,
                answer_text=INSUFFICIENT_EVIDENCE_MESSAGE,
                citations=[],
                invalid_citations=[],
                citation_validation=CitationValidation.PASS,
                model_id=self.profile.model_id,
                prompt_version=self.profile.prompt_version,
                finish_reason=finish_reason,
                usage=usage,
                answerability_status=parsed.status,
                answerability_validation=parsed.validation,
            )
            self._log_result(prepared, result)
            return result

        citations, invalid, validation, status = validate_and_map_citations(
            parsed.public_text, prepared.package.selected_evidence
        )
        if parsed.validation != AnswerabilityValidation.PASS:
            status = GenerationStatus.COMPLETED_WITH_WARNINGS
        result = GenerationResult(
            request_id=prepared.request_id,
            status=status,
            answer_text=parsed.public_text,
            citations=citations,
            invalid_citations=invalid,
            citation_validation=validation,
            model_id=self.profile.model_id,
            prompt_version=self.profile.prompt_version,
            finish_reason=finish_reason,
            usage=usage,
            answerability_status=parsed.status,
            answerability_validation=parsed.validation,
        )
        self._log_result(prepared, result)
        return result

    def _log_result(self, prepared: PreparedAnswer, result: GenerationResult) -> None:
        logger.info(
            "answer_completed",
            request_id=prepared.request_id,
            stage="FINALIZE",
            total_ms=round((perf_counter() - prepared.started) * 1000, 3),
            prompt_tokens=prepared.prompt_tokens,
            provider_input_tokens=result.usage.input_tokens if result.usage else None,
            output_tokens=result.usage.output_tokens if result.usage else None,
            citation_count=len(result.citations),
            invalid_citation_count=len(result.invalid_citations),
            generation_status=result.status.value,
            answerability_status=result.answerability_status.value if result.answerability_status else None,
            answerability_validation=result.answerability_validation.value,
            finish_reason=result.finish_reason,
            model_id=self.profile.model_id,
            prompt_version=self.profile.prompt_version,
            retrieval_ms=round(prepared.timings.get("retrieval_ms", 0), 3),
            context_build_ms=round(prepared.timings.get("context_build_ms", 0), 3),
            prompt_build_ms=round(prepared.timings.get("prompt_build_ms", 0), 3),
            prompt_token_count_ms=round(prepared.timings.get("prompt_token_count_ms", 0), 3),
            time_to_first_token_ms=(
                round(prepared.timings["time_to_first_token_ms"], 3)
                if "time_to_first_token_ms" in prepared.timings
                else None
            ),
            generation_ms=round(prepared.timings.get("generation_ms", 0), 3),
        )

    async def answer_prepared(self, prepared: PreparedAnswer) -> GenerationResult:
        if prepared.early_result is not None:
            return prepared.early_result
        generation_started = perf_counter()
        result = await self.llm_client.generate(prepared.messages, self.profile)
        prepared.timings["generation_ms"] = (perf_counter() - generation_started) * 1000
        return self._finalize(prepared, result.text, result.finish_reason, result.usage)

    async def answer(self, request_id: str, request: AnswerRequest) -> GenerationResult:
        return await self.answer_prepared(await self.prepare(request_id, request))

    async def check_provider(self, prepared: PreparedAnswer) -> None:
        if prepared.early_result is None:
            await self.llm_client.health(self.profile)

    async def stream_prepared(self, prepared: PreparedAnswer) -> AsyncIterator[tuple[str, object]]:
        if prepared.early_result is not None:
            yield "done", prepared.early_result
            return
        raw_pieces: list[str] = []
        prefix_buffer = ""
        prefix_resolved = False
        insufficient_decided = False
        marker_filter = StreamingMarkerFilter()
        strip_leading_public_whitespace = False
        finish_reason = None
        usage = None
        generation_started = perf_counter()
        first_token_seen = False
        provider_stream = self.llm_client.stream(prepared.messages, self.profile)
        try:
            async for chunk in provider_stream:
                if chunk.text:
                    raw_pieces.append(chunk.text)
                    if not first_token_seen:
                        prepared.timings["time_to_first_token_ms"] = (perf_counter() - generation_started) * 1000
                        first_token_seen = True
                    if not prefix_resolved:
                        prefix_buffer += chunk.text
                        parsed_prefix = resolved_prefix(prefix_buffer)
                        if parsed_prefix is not None:
                            prefix_resolved = True
                            if parsed_prefix.status == AnswerabilityStatus.INSUFFICIENT_EVIDENCE:
                                insufficient_decided = True
                                break
                            strip_leading_public_whitespace = True
                            visible = marker_filter.feed(parsed_prefix.public_text)
                            if strip_leading_public_whitespace:
                                visible = visible.lstrip(" \t\r\n")
                                if visible:
                                    strip_leading_public_whitespace = False
                            if visible:
                                yield "delta", visible
                        elif "\n" in prefix_buffer or len(prefix_buffer) >= 128:
                            # Missing/malformed status: continue safely under a final warning,
                            # but never leak a marker-like control fragment.
                            prefix_resolved = True
                            visible = marker_filter.feed(strip_internal_markers(prefix_buffer))
                            if visible:
                                yield "delta", visible
                    else:
                        visible = marker_filter.feed(chunk.text)
                        if strip_leading_public_whitespace:
                            visible = visible.lstrip(" \t\r\n")
                            if visible:
                                strip_leading_public_whitespace = False
                        if visible:
                            yield "delta", visible
                if chunk.done:
                    finish_reason = chunk.finish_reason
                    usage = chunk.usage
        finally:
            close = getattr(provider_stream, "aclose", None)
            if close is not None:
                await close()

        if insufficient_decided:
            prepared.timings["generation_ms"] = (perf_counter() - generation_started) * 1000
            yield "done", self._finalize(prepared, "".join(raw_pieces), finish_reason, usage)
            return

        if not prefix_resolved and prefix_buffer:
            visible = marker_filter.feed(strip_internal_markers(prefix_buffer))
            if visible:
                yield "delta", visible
        tail = marker_filter.finish()
        if tail:
            yield "delta", tail
        prepared.timings["generation_ms"] = (perf_counter() - generation_started) * 1000
        yield "done", self._finalize(prepared, "".join(raw_pieces), finish_reason, usage)
