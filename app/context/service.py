import math
from collections.abc import Sequence
from time import perf_counter
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.context.dedup import deduplicate_candidates
from app.context.exceptions import (
    ContextBuilderError,
    ContextValidationError,
    TokenCounterDependencyError,
)
from app.context.formatter import EVIDENCE_SEPARATOR, format_evidence_block
from app.context.schemas import ContextPackage, SelectedEvidence, StopReason
from app.context.token_counter import TokenCounter
from app.core.logging import get_logger
from app.retrieval.schemas import RetrievedCandidate


logger = get_logger(__name__)


class ContextBuilderService:
    """Build an exact-token-counted context without I/O or model ownership."""

    def __init__(self, token_counter: TokenCounter):
        if token_counter is None or not callable(getattr(token_counter, "count", None)):
            raise ContextValidationError(
                "VALIDATE_INPUT", "A TokenCounter dependency is required"
            )
        self.token_counter = token_counter

    def build(
        self,
        *,
        request_id: str,
        query_text: str,
        retrieved_candidates: Sequence[RetrievedCandidate | dict[str, Any]],
        context_budget_tokens: int,
    ) -> ContextPackage:
        started = perf_counter()
        candidates = self._validate_input(
            request_id,
            query_text,
            retrieved_candidates,
            context_budget_tokens,
        )
        candidate_count = len(candidates)
        tokenizer_provider = getattr(self.token_counter, "provider", None)
        tokenizer_id = getattr(self.token_counter, "tokenizer_id", None)

        logger.info(
            "context_build_started",
            stage="VALIDATE_INPUT",
            request_id=request_id,
            candidate_count=candidate_count,
            context_budget_tokens=context_budget_tokens,
            tokenizer_provider=tokenizer_provider,
            tokenizer_id=tokenizer_id,
        )

        try:
            deduplicated, duplicate_count = deduplicate_candidates(candidates)
        except Exception as exc:
            raise ContextBuilderError(
                "DEDUPLICATION", "Unexpected context deduplication error"
            ) from exc

        selected: list[SelectedEvidence] = []
        context_pieces: list[str] = []
        accumulated_tokens = 0
        stop_reason = StopReason.NONE
        budget_exhausted = False

        for candidate in deduplicated:
            source_id = f"S{len(selected) + 1}"
            try:
                block = format_evidence_block(candidate, source_id)
            except Exception as exc:
                raise ContextBuilderError(
                    "FORMAT_EVIDENCE", "Unable to format retrieved evidence"
                ) from exc

            block_token_count = self._count(block)
            piece = block if not selected else EVIDENCE_SEPARATOR + block
            piece_token_count = self._count(piece)
            prospective_context = "".join(context_pieces) + piece
            prospective_exact_count = self._count(prospective_context)

            # Preserve the frozen piece-accounting rule while also protecting
            # exactness for tokenizers whose encodings are not additive across
            # independently counted string boundaries.
            if (
                accumulated_tokens + piece_token_count > context_budget_tokens
                or prospective_exact_count > context_budget_tokens
            ):
                budget_exhausted = True
                stop_reason = (
                    StopReason.TOP_EVIDENCE_EXCEEDS_CONTEXT_BUDGET
                    if not selected
                    else StopReason.TOKEN_BUDGET
                )
                break

            context_pieces.append(piece)
            accumulated_tokens = prospective_exact_count
            selected.append(
                SelectedEvidence(
                    source_id=source_id,
                    chunk_id=candidate.chunk_id,
                    document_id=candidate.document_id,
                    content_text=candidate.content_text,
                    metadata_json=candidate.metadata_json,
                    provenance_json=candidate.provenance_json,
                    retrieval_final_rank=candidate.retrieval_final_rank,
                    context_candidate_order=candidate.context_candidate_order,
                    candidate_origin=candidate.candidate_origin,
                    legal_unit_id=candidate.legal_unit_id,
                    hierarchy_relation=candidate.hierarchy_relation,
                    hierarchy_depth=candidate.hierarchy_depth,
                    anchor_chunk_id=candidate.anchor_chunk_id,
                    anchor_legal_unit_id=candidate.anchor_legal_unit_id,
                    anchor_retrieval_final_rank=candidate.anchor_retrieval_final_rank,
                    hierarchy_anchor_references=candidate.hierarchy_anchor_references,
                    dense_score=candidate.dense_score,
                    dense_rank=candidate.dense_rank,
                    lexical_score=candidate.lexical_score,
                    lexical_rank=candidate.lexical_rank,
                    fusion_score=candidate.fusion_score,
                    token_count=block_token_count,
                )
            )

        context_text = "".join(context_pieces)
        exact_context_count = self._count(context_text)
        if exact_context_count != accumulated_tokens:
            raise ContextBuilderError(
                "FINALIZE",
                "TokenCounter produced inconsistent counts for identical context text",
            )
        if exact_context_count > context_budget_tokens:
            raise ContextBuilderError(
                "FINALIZE", "Final context exceeds the injected token budget"
            )

        selected_count = len(selected)
        dropped_count = candidate_count - selected_count
        context_build_ms = (perf_counter() - started) * 1000
        budget_utilization = exact_context_count / context_budget_tokens

        package = ContextPackage(
            request_id=request_id,
            query_text=query_text,
            context_text=context_text,
            selected_evidence=selected,
            context_token_count=exact_context_count,
            context_budget_tokens=context_budget_tokens,
            candidate_count=candidate_count,
            duplicate_count=duplicate_count,
            selected_count=selected_count,
            dropped_count=dropped_count,
            budget_exhausted=budget_exhausted,
            stop_reason=stop_reason,
        )
        logger.info(
            "context_build_completed",
            stage="FINALIZE",
            request_id=request_id,
            candidate_count=candidate_count,
            duplicate_count=duplicate_count,
            selected_count=selected_count,
            dropped_count=dropped_count,
            context_budget_tokens=context_budget_tokens,
            context_token_count=exact_context_count,
            budget_utilization=round(budget_utilization, 6),
            budget_exhausted=budget_exhausted,
            stop_reason=stop_reason.value,
            context_build_ms=round(context_build_ms, 3),
            tokenizer_provider=tokenizer_provider,
            tokenizer_id=tokenizer_id,
        )
        return package

    def _count(self, text: str) -> int:
        try:
            count = self.token_counter.count(text)
        except ContextBuilderError:
            raise
        except Exception as exc:
            raise TokenCounterDependencyError(
                "TOKEN_COUNTING", "TokenCounter dependency is unavailable"
            ) from exc
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise TokenCounterDependencyError(
                "TOKEN_COUNTING", "TokenCounter returned an invalid token count"
            )
        return count

    @staticmethod
    def _validate_input(
        request_id: str,
        query_text: str,
        retrieved_candidates: Sequence[RetrievedCandidate | dict[str, Any]],
        context_budget_tokens: int,
    ) -> list[RetrievedCandidate]:
        if not isinstance(request_id, str) or not request_id.strip():
            raise ContextValidationError(
                "VALIDATE_INPUT", "request_id must not be empty"
            )
        if not isinstance(query_text, str) or not query_text.strip():
            raise ContextValidationError(
                "VALIDATE_INPUT", "query_text must not be empty"
            )
        if (
            isinstance(context_budget_tokens, bool)
            or not isinstance(context_budget_tokens, int)
            or context_budget_tokens <= 0
        ):
            raise ContextValidationError(
                "VALIDATE_INPUT", "context_budget_tokens must be greater than zero"
            )
        if isinstance(retrieved_candidates, (str, bytes)) or not isinstance(
            retrieved_candidates, Sequence
        ):
            raise ContextValidationError(
                "VALIDATE_INPUT", "retrieved_candidates must be a sequence"
            )

        validated: list[RetrievedCandidate] = []
        previous_order = 0
        for index, raw_candidate in enumerate(retrieved_candidates):
            try:
                candidate = RetrievedCandidate.model_validate(raw_candidate)
            except ValidationError as exc:
                raise ContextValidationError(
                    "VALIDATE_INPUT", f"Invalid candidate at index {index}"
                ) from exc

            if not candidate.content_text.strip():
                raise ContextValidationError(
                    "VALIDATE_INPUT", f"Candidate at index {index} has empty content_text"
                )
            try:
                UUID(candidate.chunk_id)
                UUID(candidate.document_id)
            except (ValueError, TypeError, AttributeError) as exc:
                raise ContextValidationError(
                    "VALIDATE_INPUT", f"Candidate at index {index} has an invalid UUID"
                ) from exc
            if candidate.context_candidate_order <= previous_order:
                raise ContextValidationError(
                    "VALIDATE_INPUT",
                    "Candidates must be ordered by strictly increasing context_candidate_order",
                )
            if candidate.dense_rank is not None and candidate.dense_rank <= 0:
                raise ContextValidationError(
                    "VALIDATE_INPUT", "dense_rank must be greater than zero"
                )
            if candidate.lexical_rank is not None and candidate.lexical_rank <= 0:
                raise ContextValidationError(
                    "VALIDATE_INPUT", "lexical_rank must be greater than zero"
                )
            if candidate.fusion_score is not None and not math.isfinite(candidate.fusion_score):
                raise ContextValidationError(
                    "VALIDATE_INPUT", "fusion_score must be finite"
                )
            previous_order = candidate.context_candidate_order
            validated.append(candidate)

        return validated
