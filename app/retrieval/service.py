from dataclasses import dataclass
from time import perf_counter
from uuid import UUID

from sqlalchemy.exc import InterfaceError, OperationalError, SQLAlchemyError
from structlog.contextvars import get_contextvars

from app.core.config import settings
from app.core.logging import get_logger
from app.retrieval.exceptions import (
    QueryInputTooLongError,
    RetrievalDependencyError,
    RetrievalError,
    RetrievalValidationError,
)
from app.retrieval.query_embedder import QueryEmbedder
from app.retrieval.hierarchy_expander import LegalHierarchyExpander
from app.retrieval.hierarchy_repository import HierarchyRepository
from app.retrieval.hierarchy_types import (
    CandidateOrigin,
    HierarchyExpansionDiagnostics,
    HierarchyExpansionStatus,
)
from app.retrieval.repository import RetrievalRepository
from app.retrieval.rrf import reciprocal_rank_fusion
from app.retrieval.schemas import RetrievedCandidate, RetrievalRequest
from app.auth.access import DocumentAccessService
from app.auth.scope import InternalRetrievalScope, RetrievalAccessScope, UserRetrievalScope


logger = get_logger(__name__)


@dataclass(frozen=True)
class RetrievalParameters:
    query_text: str
    top_k_dense: int
    top_k_lexical: int
    top_k_final: int
    rrf_k: int
    document_ids: tuple[UUID, ...]


def _positive_bounded(name: str, value: int, maximum: int) -> None:
    if value <= 0:
        raise RetrievalValidationError("VALIDATE_QUERY", f"{name} must be greater than zero")
    if value > maximum:
        raise RetrievalValidationError(
            "VALIDATE_QUERY", f"{name} exceeds the safety limit of {maximum}"
        )


def validate_request(request: RetrievalRequest) -> RetrievalParameters:
    query_text = request.query_text.strip()
    if not query_text:
        raise RetrievalValidationError(
            "VALIDATE_QUERY", "query_text must not be empty or whitespace-only"
        )

    _positive_bounded("top_k_dense", request.top_k_dense, settings.RETRIEVAL_MAX_TOP_K_DENSE)
    _positive_bounded(
        "top_k_lexical", request.top_k_lexical, settings.RETRIEVAL_MAX_TOP_K_LEXICAL
    )
    _positive_bounded("top_k_final", request.top_k_final, settings.RETRIEVAL_MAX_TOP_K_FINAL)
    _positive_bounded("rrf_k", request.rrf_k, settings.RETRIEVAL_MAX_RRF_K)

    raw_document_ids = request.document_ids or []
    if len(raw_document_ids) > settings.RETRIEVAL_MAX_DOCUMENT_IDS:
        raise RetrievalValidationError(
            "VALIDATE_QUERY",
            f"document_ids exceeds the safety limit of {settings.RETRIEVAL_MAX_DOCUMENT_IDS}",
        )

    deduplicated: list[UUID] = []
    seen: set[UUID] = set()
    for value in raw_document_ids:
        try:
            document_id = UUID(value)
        except (ValueError, TypeError, AttributeError) as exc:
            raise RetrievalValidationError(
                "VALIDATE_QUERY", f"Invalid document UUID: {value}"
            ) from exc
        if document_id not in seen:
            seen.add(document_id)
            deduplicated.append(document_id)

    return RetrievalParameters(
        query_text=query_text,
        top_k_dense=request.top_k_dense,
        top_k_lexical=request.top_k_lexical,
        top_k_final=request.top_k_final,
        rrf_k=request.rrf_k,
        document_ids=tuple(deduplicated),
    )


class RetrievalService:
    def __init__(self, db, embedder=None, repository=None, hierarchy_expander=None, access_scope: RetrievalAccessScope | None = None):
        self.db = db
        self.access_scope = access_scope or InternalRetrievalScope("trusted-internal")
        self.repository = repository or RetrievalRepository(db, self.access_scope)
        self.embedder = embedder
        self.hierarchy_expander = hierarchy_expander
        if self.hierarchy_expander is None and db is not None:
            self.hierarchy_expander = LegalHierarchyExpander(
                HierarchyRepository(db),
                enabled=settings.RETRIEVAL_HIERARCHY_ENABLED,
                max_anchors=settings.RETRIEVAL_HIERARCHY_MAX_ANCHORS,
                max_children_per_anchor=(
                    settings.RETRIEVAL_HIERARCHY_MAX_CHILDREN_PER_ANCHOR
                ),
                max_candidates_added=(
                    settings.RETRIEVAL_HIERARCHY_MAX_CANDIDATES_ADDED
                ),
                depth=settings.RETRIEVAL_HIERARCHY_DEPTH,
            )
        self.last_base_candidates: list[RetrievedCandidate] = []
        self.last_hierarchy_diagnostics = HierarchyExpansionDiagnostics(
            status=HierarchyExpansionStatus.DISABLED,
            enabled=False,
            reason_codes=["HIERARCHY_EXPANDER_UNAVAILABLE"],
        )

    def require_document_scope(self, document_ids: tuple[UUID, ...]) -> None:
        if document_ids and isinstance(self.access_scope, UserRetrievalScope):
            DocumentAccessService(self.db).require_all_accessible(self.access_scope.user_id, document_ids)

    def retrieve(self, params: RetrievalParameters) -> list[dict]:
        self.require_document_scope(params.document_ids)
        request_id = get_contextvars().get("request_id", "unbound")
        total_started = perf_counter()
        timings: dict[str, float] = {}
        common = {
            "request_id": request_id,
            "query_length": len(params.query_text),
            "document_filter_count": len(params.document_ids),
            "top_k_dense": params.top_k_dense,
            "top_k_lexical": params.top_k_lexical,
            "top_k_final": params.top_k_final,
            "rrf_k": params.rrf_k,
        }
        logger.info("retrieval_started", stage="VALIDATE_QUERY", **common)

        try:
            started = perf_counter()
            embedder = self.embedder or QueryEmbedder.get_instance()
            query_vector = embedder.encode(params.query_text)
            timings["query_embedding_ms"] = (perf_counter() - started) * 1000
            logger.info(
                "retrieval_stage_completed",
                stage="QUERY_EMBEDDING",
                query_embedding_ms=round(timings["query_embedding_ms"], 3),
                **common,
            )

            started = perf_counter()
            dense = self.repository.dense_search(
                query_vector, params.top_k_dense, params.document_ids
            )
            timings["dense_search_ms"] = (perf_counter() - started) * 1000
            logger.info(
                "retrieval_stage_completed",
                stage="DENSE_SEARCH",
                dense_candidate_count=len(dense),
                dense_search_ms=round(timings["dense_search_ms"], 3),
                **common,
            )

            started = perf_counter()
            lexical = self.repository.lexical_search(
                params.query_text, params.top_k_lexical, params.document_ids
            )
            timings["lexical_search_ms"] = (perf_counter() - started) * 1000
            logger.info(
                "retrieval_stage_completed",
                stage="LEXICAL_SEARCH",
                lexical_candidate_count=len(lexical),
                lexical_search_ms=round(timings["lexical_search_ms"], 3),
                **common,
            )

            started = perf_counter()
            fused = reciprocal_rank_fusion(
                dense, lexical, params.rrf_k, params.top_k_final
            )
            timings["fusion_ms"] = (perf_counter() - started) * 1000
            overlap_count = len({c.chunk_id for c in dense} & {c.chunk_id for c in lexical})
            logger.info(
                "retrieval_stage_completed",
                stage="FUSION",
                overlap_count=overlap_count,
                fused_candidate_count=len({c.chunk_id for c in dense} | {c.chunk_id for c in lexical}),
                final_candidate_count=len(fused),
                fusion_ms=round(timings["fusion_ms"], 3),
                **common,
            )

            started = perf_counter()
            hydrated = self.repository.hydrate([candidate.chunk_id for candidate in fused])
            timings["hydration_ms"] = (perf_counter() - started) * 1000
        except QueryInputTooLongError:
            raise
        except RetrievalError:
            raise
        except (OperationalError, InterfaceError) as exc:
            stage = self._stage_from_timings(timings)
            raise RetrievalDependencyError(stage, "PostgreSQL is unavailable") from exc
        except SQLAlchemyError as exc:
            stage = self._stage_from_timings(timings)
            raise RetrievalError(stage, "Unexpected internal retrieval error") from exc
        except Exception as exc:
            stage = self._stage_from_timings(timings)
            if stage == "QUERY_EMBEDDING":
                raise RetrievalDependencyError(
                    stage, "Embedding model is unavailable"
                ) from exc
            raise RetrievalError(stage, "Unexpected internal retrieval error") from exc

        missing = [str(candidate.chunk_id) for candidate in fused if candidate.chunk_id not in hydrated]
        if missing:
            raise RetrievalError("HYDRATION", "One or more selected chunks could not be hydrated")

        base_candidates: list[RetrievedCandidate] = []
        for candidate in fused:
            chunk = hydrated[candidate.chunk_id]
            base_candidates.append(
                RetrievedCandidate(
                    chunk_id=str(candidate.chunk_id),
                    document_id=str(chunk.document_id),
                    content_text=chunk.content_text,
                    metadata_json=chunk.metadata_json,
                    provenance_json=chunk.provenance_json,
                    dense_score=candidate.dense_score,
                    dense_rank=candidate.dense_rank,
                    lexical_score=candidate.lexical_score,
                    lexical_rank=candidate.lexical_rank,
                    fusion_score=candidate.fusion_score,
                    retrieval_final_rank=candidate.final_rank,
                    final_rank=candidate.final_rank,
                    context_candidate_order=candidate.final_rank,
                    candidate_origin=CandidateOrigin.RETRIEVAL,
                    legal_unit_id=(
                        str(chunk.legal_unit_id) if chunk.legal_unit_id is not None else None
                    ),
                )
            )

        self.last_base_candidates = base_candidates
        if self.hierarchy_expander is None:
            results_models = base_candidates
            hierarchy = HierarchyExpansionDiagnostics(
                status=HierarchyExpansionStatus.DISABLED,
                enabled=False,
                reason_codes=["HIERARCHY_EXPANDER_UNAVAILABLE"],
                base_anchor_count=len(base_candidates),
            )
        else:
            results_models, hierarchy = self.hierarchy_expander.expand(
                base_candidates,
                params.document_ids,
                canonical_anchor_window=(
                    params.top_k_final == settings.RETRIEVAL_TOP_K_FINAL_DEFAULT
                ),
            )
        self.last_hierarchy_diagnostics = hierarchy
        timings["hierarchy_lookup_ms"] = hierarchy.hierarchy_lookup_ms
        timings["hierarchy_total_ms"] = hierarchy.hierarchy_total_ms
        results = [item.model_dump(mode="json") for item in results_models]

        total_ms = (perf_counter() - total_started) * 1000
        logger.info(
            "retrieval_completed",
            stage="HIERARCHY_ORDERING",
            dense_candidate_count=len(dense),
            lexical_candidate_count=len(lexical),
            overlap_count=overlap_count,
            fused_candidate_count=len({c.chunk_id for c in dense} | {c.chunk_id for c in lexical}),
            final_candidate_count=len(results),
            hierarchy_status=hierarchy.status.value,
            hierarchy_children_added=hierarchy.children_added,
            hierarchy_fallback_used=hierarchy.fallback_used,
            hierarchy_global_cap_reached=hierarchy.global_cap_reached,
            total_retrieval_ms=round(total_ms, 3),
            **{key: round(value, 3) for key, value in timings.items()},
            **common,
        )
        return results

    @staticmethod
    def _stage_from_timings(timings: dict[str, float]) -> str:
        if "query_embedding_ms" not in timings:
            return "QUERY_EMBEDDING"
        if "dense_search_ms" not in timings:
            return "DENSE_SEARCH"
        if "lexical_search_ms" not in timings:
            return "LEXICAL_SEARCH"
        if "fusion_ms" not in timings:
            return "FUSION"
        return "HYDRATION"
