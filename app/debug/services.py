import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.generation.profile import get_generation_profile
from app.generation.runtime import get_llm_client
from app.generation.schemas import AnswerRequest, GenerationResult
from app.indexing.constants import CANONICAL_INDEX_VERSION
from app.orchestration.answer_service import AnswerService
from app.retrieval.repository import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    RetrievalRepository,
)
from app.retrieval.service import RetrievalService
from app.auth.scope import RetrievalAccessScope, UserRetrievalScope
from evaluation.context_metrics import context_retention
from evaluation.dataset_validator import load_dataset
from evaluation.generation_metrics import classify_failure, expected_source_match
from evaluation.v2_metrics import evidence_set_metrics

from app.debug.schemas import (
    CandidateSnapshot,
    ChunkDetail,
    ContextSnapshot,
    DebugRagRequest,
    DebugTrace,
    DocumentDetailView,
    DocumentPipelineView,
    EvaluationCaseDetail,
    EvaluationCaseView,
    EvaluationComparison,
    EvaluationDiagnosis,
    EvaluationExpectedSnapshot,
    EvaluationSummary,
    GenerationSnapshot,
    LexicalMode,
    PipelineStageSnapshot,
    RetrievalSnapshot,
    SelectedEvidenceSnapshot,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = PROJECT_ROOT / "evaluation" / "datasets" / "legal_eval_v1.json"
REPORT_PATH = PROJECT_ROOT / "evaluation" / "reports" / "legal_eval_v1_after_quality_fixes.json"
COMPARISON_PATH = PROJECT_ROOT / "evaluation" / "reports" / "quality_fix_before_after_v1.json"
FROZEN_DATASET_SHA256 = "afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245"
V2_DATASET_PATH = PROJECT_ROOT / "evaluation" / "datasets" / "legal_eval_v2.json"
V2_REPORT_PATH = PROJECT_ROOT / "evaluation" / "reports" / "legal_eval_v2_baseline.json"
V2_FROZEN_DATASET_SHA256 = "ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842"
PREVIEW_LIMIT = 320


def dataset_sha256() -> str:
    return hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()


def assert_frozen_dataset() -> str:
    actual = dataset_sha256()
    if actual != FROZEN_DATASET_SHA256:
        raise RuntimeError("Frozen evaluation dataset hash mismatch")
    return actual


def _preview(value: str) -> str:
    compact = " ".join(value.split())
    return compact if len(compact) <= PREVIEW_LIMIT else compact[: PREVIEW_LIMIT - 1] + "…"


class CapturingRepository:
    """Transparent read-only wrapper around the frozen Block 4 repository."""

    def __init__(self, delegate: RetrievalRepository):
        self.delegate = delegate
        self.dense = []
        self.lexical = []
        self.final_results: list[dict[str, Any]] = []
        self.timings: dict[str, float] = {}

    def dense_search(self, *args):
        started = perf_counter()
        self.dense = self.delegate.dense_search(*args)
        self.timings["dense_search_ms"] = (perf_counter() - started) * 1000
        return self.dense

    def lexical_search(self, *args):
        started = perf_counter()
        self.lexical = self.delegate.lexical_search(*args)
        self.timings["lexical_search_ms"] = (perf_counter() - started) * 1000
        return self.lexical

    def hydrate(self, *args):
        started = perf_counter()
        hydrated = self.delegate.hydrate(*args)
        self.timings["hydration_ms"] = (perf_counter() - started) * 1000
        return hydrated


class CapturingRetrievalService(RetrievalService):
    def __init__(self, db, capture: CapturingRepository, access_scope: RetrievalAccessScope | None = None):
        super().__init__(db, repository=capture, access_scope=access_scope)
        self.capture = capture

    def retrieve(self, params):
        results = super().retrieve(params)
        self.capture.final_results = results
        self.capture.base_results = [
            item.model_dump(mode="json") for item in self.last_base_candidates
        ]
        self.capture.hierarchy = self.last_hierarchy_diagnostics.as_dict()
        return results


class DebugRagService:
    def __init__(self, db, llm_client=None, access_scope: RetrievalAccessScope | None = None):
        self.db = db
        self.access_scope = access_scope
        self.llm_client = llm_client or get_llm_client()
        self.profile = get_generation_profile()
        self.artifacts = EvaluationArtifactService()

    async def run(self, request_id: str, request: DebugRagRequest) -> DebugTrace:
        started = perf_counter()
        expected = None
        case = None
        document_ids = request.document_ids
        if request.evaluation_case_id:
            self.artifacts = EvaluationArtifactService.for_case(request.evaluation_case_id)
            case = self.artifacts.dataset_case(request.evaluation_case_id)
            if " ".join(request.query_text.split()) != " ".join(case.question.split()):
                raise ValueError("query_text must match the immutable evaluation case question")
            if document_ids is not None and document_ids != case.document_ids:
                raise ValueError("document_ids must match the immutable evaluation case filter")
            document_ids = case.document_ids
            expected = EvaluationExpectedSnapshot(
                case_id=case.case_id,
                category=case.category.value,
                answerable=case.answerable,
                expected_document_ids=case.expected_document_ids,
                acceptable_evidence_sets=case.acceptable_evidence_sets,
                source_reference=case.source_reference,
                notes=case.notes,
            )

        capture = CapturingRepository(RetrievalRepository(self.db, self.access_scope))
        retrieval_service = CapturingRetrievalService(self.db, capture, self.access_scope)
        answer_service = AnswerService(retrieval_service, self.llm_client, self.profile)
        prepared = await answer_service.prepare(
            request_id,
            AnswerRequest(query_text=request.query_text, document_ids=document_ids),
        )

        result: GenerationResult | None = None
        async for event, value in answer_service.stream_prepared(prepared):
            if event == "done":
                result = value
        if result is None:
            raise RuntimeError("Generation completed without an authoritative result")

        retrieved = self._retrieved_from_package_and_capture(prepared.package, capture)
        previews = self._candidate_content(capture, retrieved)
        lexical_mode = self._lexical_mode(request.query_text, document_ids or [], capture.lexical)
        retrieval_snapshot = self._retrieval_snapshot(capture, retrieved, previews, lexical_mode)
        context_snapshot = self._context_snapshot(prepared.package)
        generation_snapshot = self._generation_snapshot(result, prepared)
        diagnosis = self._diagnose(case, retrieved, prepared.package, result) if case else None
        timings = {
            "retrieval_ms": prepared.timings.get("retrieval_ms", 0.0),
            "context_ms": prepared.timings.get("context_build_ms", 0.0),
            "generation_ms": prepared.timings.get("generation_ms", 0.0),
            "time_to_first_token_ms": prepared.timings.get("time_to_first_token_ms", 0.0),
            "total_ms": (perf_counter() - started) * 1000,
        }
        return DebugTrace(
            request_id=request_id,
            query_text=request.query_text,
            document_ids=list(document_ids or []),
            retrieval=retrieval_snapshot,
            context=context_snapshot,
            generation=generation_snapshot,
            timings_ms=timings,
            expected=expected,
            diagnosis=diagnosis,
        )

    @staticmethod
    def _retrieved_from_package_and_capture(package, capture) -> list[dict[str, Any]]:
        # Captured directly from the sole production RetrievalService execution.
        return list(getattr(capture, "final_results", []))

    def _candidate_content(self, capture, retrieved):
        ids = {item.chunk_id for item in capture.dense + capture.lexical}
        ids.update(UUID(item["chunk_id"]) for item in retrieved)
        if not ids:
            return {}
        rows = self.db.execute(
            text("SELECT id, content_text FROM chunks WHERE id = ANY(CAST(:ids AS uuid[]))"),
            {"ids": [str(value) for value in ids]},
        ).mappings().all()
        return {str(row["id"]): row["content_text"] for row in rows}

    def _lexical_mode(self, query_text: str, document_ids: list[str], lexical) -> LexicalMode:
        if not lexical:
            return LexicalMode.NO_LEXICAL_MATCH
        document_filter = ""
        params: dict[str, Any] = {
            "query_text": query_text,
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dimension": EMBEDDING_DIMENSION,
            "index_version": CANONICAL_INDEX_VERSION,
        }
        if document_ids:
            document_filter = "AND ci.document_id = ANY(CAST(:document_ids AS uuid[]))"
            params["document_ids"] = document_ids
        authorization_filter = ""
        if isinstance(self.access_scope, UserRetrievalScope):
            authorization_filter = """
              AND (
                EXISTS (SELECT 1 FROM document_access_grants dag WHERE dag.document_id=ci.document_id AND dag.user_id=:scope_user_id)
                OR EXISTS (SELECT 1 FROM global_document_access gda WHERE gda.document_id=ci.document_id)
              )
            """
            params["scope_user_id"] = str(self.access_scope.user_id)
        strict = self.db.execute(
            text(
                f"""
                SELECT EXISTS (
                    SELECT 1 FROM chunk_indexes ci
                    WHERE ci.lexical_tsv @@ websearch_to_tsquery('simple', :query_text)
                      AND ci.embedding_model = :embedding_model
                      AND ci.embedding_dimension = :embedding_dimension
                      AND ci.index_version = :index_version
                      {authorization_filter}
                      {document_filter}
                )
                """
            ),
            params,
        ).scalar_one()
        return LexicalMode.STRICT_MATCH if strict else LexicalMode.SELECTIVE_FALLBACK

    @staticmethod
    def _retrieval_snapshot(capture, retrieved, previews, lexical_mode):
        def branch(item, kind):
            data = asdict(item)
            return CandidateSnapshot(
                chunk_id=str(data["chunk_id"]),
                document_id=str(data["document_id"]),
                dense_rank=data.get("dense_rank"),
                dense_score=data.get("dense_score"),
                lexical_rank=data.get("lexical_rank"),
                lexical_score=data.get("lexical_score"),
                content_preview=_preview(previews.get(str(data["chunk_id"]), "")),
            )

        final = [
            CandidateSnapshot(
                chunk_id=item["chunk_id"],
                document_id=item["document_id"],
                dense_rank=item["dense_rank"],
                dense_score=item["dense_score"],
                lexical_rank=item["lexical_rank"],
                lexical_score=item["lexical_score"],
                fusion_score=item["fusion_score"],
                final_rank=item["final_rank"],
                retrieval_final_rank=item["retrieval_final_rank"],
                context_candidate_order=item["context_candidate_order"],
                candidate_origin=item["candidate_origin"],
                legal_unit_id=item["legal_unit_id"],
                hierarchy_relation=item["hierarchy_relation"],
                hierarchy_depth=item["hierarchy_depth"],
                anchor_chunk_id=item["anchor_chunk_id"],
                anchor_legal_unit_id=item["anchor_legal_unit_id"],
                anchor_retrieval_final_rank=item["anchor_retrieval_final_rank"],
                hierarchy_anchor_references=item["hierarchy_anchor_references"],
                content_preview=_preview(item["content_text"]),
                content_text=item["content_text"],
                metadata_json=item["metadata_json"],
                provenance_json=item["provenance_json"],
            )
            for item in retrieved
        ]
        dense_ids = {str(item.chunk_id) for item in capture.dense}
        lexical_ids = {str(item.chunk_id) for item in capture.lexical}
        base = [
            CandidateSnapshot(
                chunk_id=item["chunk_id"],
                document_id=item["document_id"],
                dense_rank=item["dense_rank"],
                dense_score=item["dense_score"],
                lexical_rank=item["lexical_rank"],
                lexical_score=item["lexical_score"],
                fusion_score=item["fusion_score"],
                final_rank=item["final_rank"],
                retrieval_final_rank=item["retrieval_final_rank"],
                context_candidate_order=item["context_candidate_order"],
                candidate_origin=item["candidate_origin"],
                legal_unit_id=item["legal_unit_id"],
                content_preview=_preview(item["content_text"]),
                content_text=item["content_text"],
                metadata_json=item["metadata_json"],
                provenance_json=item["provenance_json"],
            )
            for item in getattr(capture, "base_results", [])
        ]
        return RetrievalSnapshot(
            dense_candidates=[branch(item, "dense") for item in capture.dense],
            lexical_candidates=[branch(item, "lexical") for item in capture.lexical],
            final_candidates=final,
            rrf_candidates=base,
            hierarchy_candidates=[
                item for item in final if item.candidate_origin == "HIERARCHY_CHILD"
            ],
            final_context_candidates=final,
            hierarchy=getattr(capture, "hierarchy", {}),
            dense_candidate_count=len(capture.dense),
            lexical_candidate_count=len(capture.lexical),
            overlap_count=len(dense_ids & lexical_ids),
            lexical_mode=lexical_mode,
            timings_ms=dict(capture.timings),
        )

    @staticmethod
    def _context_snapshot(package):
        return ContextSnapshot(
            candidate_count=package.candidate_count,
            duplicate_count=package.duplicate_count,
            selected_count=package.selected_count,
            dropped_count=package.dropped_count,
            context_token_count=package.context_token_count,
            context_budget_tokens=package.context_budget_tokens,
            budget_utilization_percent=round(
                100 * package.context_token_count / package.context_budget_tokens, 2
            ),
            budget_exhausted=package.budget_exhausted,
            stop_reason=package.stop_reason.value,
            selected_evidence=[
                SelectedEvidenceSnapshot(
                    source_id=item.source_id,
                    retrieval_final_rank=item.retrieval_final_rank,
                    context_candidate_order=item.context_candidate_order,
                    candidate_origin=item.candidate_origin.value,
                    legal_unit_id=item.legal_unit_id,
                    hierarchy_relation=(
                        item.hierarchy_relation.value if item.hierarchy_relation else None
                    ),
                    hierarchy_depth=item.hierarchy_depth,
                    anchor_chunk_id=item.anchor_chunk_id,
                    anchor_legal_unit_id=item.anchor_legal_unit_id,
                    anchor_retrieval_final_rank=item.anchor_retrieval_final_rank,
                    chunk_id=item.chunk_id,
                    document_id=item.document_id,
                    token_count=item.token_count,
                    content_text=item.content_text,
                    metadata_json=item.metadata_json,
                    provenance_json=item.provenance_json,
                    dense_rank=item.dense_rank,
                    lexical_rank=item.lexical_rank,
                    fusion_score=item.fusion_score,
                )
                for item in package.selected_evidence
            ],
        )

    @staticmethod
    def _generation_snapshot(result, prepared):
        ranks = {item.source_id: item.retrieval_final_rank for item in prepared.package.selected_evidence}
        return GenerationSnapshot(
            status=result.status.value,
            answerability_status=result.answerability_status.value if result.answerability_status else None,
            answerability_validation=result.answerability_validation.value,
            answer_text=result.answer_text,
            citations=[
                {
                    **item.model_dump(mode="json"),
                    "retrieval_final_rank": ranks.get(item.source_id),
                }
                for item in result.citations
            ],
            invalid_citations=result.invalid_citations,
            citation_validation=result.citation_validation.value,
            model_id=result.model_id,
            prompt_version=result.prompt_version,
            finish_reason=result.finish_reason,
            usage=result.usage.model_dump(mode="json") if result.usage else None,
            prompt_token_count=prepared.prompt_tokens,
            context_token_count=prepared.package.context_token_count,
            generation_ms=prepared.timings.get("generation_ms"),
            time_to_first_token_ms=prepared.timings.get("time_to_first_token_ms"),
        )

    @staticmethod
    def _diagnose(case, retrieved, package, result):
        final_ids = [item["chunk_id"] for item in retrieved]
        selected_ids = [item.chunk_id for item in package.selected_evidence]
        if case.case_id.startswith("v2_"):
            if not case.answerable:
                return (
                    EvaluationDiagnosis.PASS
                    if result.status.value == "INSUFFICIENT_EVIDENCE"
                    else EvaluationDiagnosis.UNSUPPORTED_ANSWER
                )
            retrieval = evidence_set_metrics(final_ids, case.acceptable_evidence_sets)
            if not retrieval["complete"]:
                if retrieval["partial"]:
                    return EvaluationDiagnosis.PARTIAL_MULTI_EVIDENCE_RETRIEVAL
                final_documents = {item["document_id"] for item in retrieved}
                if not final_documents.intersection(case.expected_document_ids):
                    return EvaluationDiagnosis.WRONG_DOCUMENT
                return EvaluationDiagnosis.RETRIEVAL_MISS
            context = evidence_set_metrics(selected_ids, case.acceptable_evidence_sets)
            if not context["complete"]:
                return EvaluationDiagnosis.CONTEXT_DROP
            if result.status.value == "INSUFFICIENT_EVIDENCE":
                return EvaluationDiagnosis.FALSE_ABSTENTION
            if result.citation_validation.value == "INVALID_REFERENCES":
                return EvaluationDiagnosis.GENERATION_INVALID_CITATION
            if result.citation_validation.value == "MISSING_CITATIONS":
                return EvaluationDiagnosis.GENERATION_MISSING_CITATION
            cited = evidence_set_metrics(
                [item.chunk_id for item in result.citations], case.acceptable_evidence_sets
            )
            return (
                EvaluationDiagnosis.PASS
                if cited["complete"]
                else EvaluationDiagnosis.GENERATION_WRONG_SOURCE
            )
        retrieved_found, retained, _ = (
            context_retention(final_ids, selected_ids, case.acceptable_evidence_sets)
            if case.answerable
            else (False, False, False)
        )
        source_match = (
            expected_source_match(
                [item.chunk_id for item in result.citations], case.acceptable_evidence_sets
            )
            if case.answerable
            else None
        )
        failure = classify_failure(
            answerable=case.answerable,
            retrieval_found=retrieved_found,
            context_retained=retained,
            status=result.status.value,
            answer_text=result.answer_text,
            citation_validation=result.citation_validation.value,
            expected_citation_match=source_match,
        )
        if failure is None:
            return EvaluationDiagnosis.PASS
        mapping = {
            "INSUFFICIENT_EVIDENCE_FALSE_NEGATIVE": EvaluationDiagnosis.FALSE_ABSTENTION,
            "OTHER": EvaluationDiagnosis.AMBIGUOUS,
            "MULTIPLE_AMBIGUOUS": EvaluationDiagnosis.AMBIGUOUS,
        }
        if failure.value in mapping:
            return mapping[failure.value]
        return EvaluationDiagnosis(failure.value)


class EvaluationArtifactService:
    def __init__(self, dataset_id: str = "legal_eval_v1"):
        if dataset_id == "legal_eval_v1":
            self.dataset_path = DATASET_PATH
            self.report_path = REPORT_PATH
            self.comparison_path = COMPARISON_PATH
            self.frozen_sha256 = FROZEN_DATASET_SHA256
        elif dataset_id == "legal_eval_v2":
            self.dataset_path = V2_DATASET_PATH
            self.report_path = V2_REPORT_PATH
            self.comparison_path = None
            self.frozen_sha256 = V2_FROZEN_DATASET_SHA256
        else:
            raise ValueError("Unknown evaluation dataset")
        actual = hashlib.sha256(self.dataset_path.read_bytes()).hexdigest()
        if actual != self.frozen_sha256:
            raise RuntimeError(f"Frozen {dataset_id} dataset hash mismatch")
        self.dataset_id = dataset_id
        self.dataset = load_dataset(self.dataset_path)

    @classmethod
    def for_case(cls, case_id: str):
        dataset_id = "legal_eval_v2" if case_id.startswith("v2_") else "legal_eval_v1"
        return cls(dataset_id)

    @staticmethod
    def _json(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Evaluation artifact unavailable: {path.name}")
        return json.loads(path.read_text(encoding="utf-8"))

    def dataset_case(self, case_id: str):
        case = next((item for item in self.dataset.cases if item.case_id == case_id), None)
        if case is None:
            raise KeyError(case_id)
        return case

    def summary(self) -> EvaluationSummary:
        report = self._json(self.report_path)
        if self.comparison_path:
            known_limitations = self._json(self.comparison_path).get("known_limitations", [])
        else:
            known_limitations = [
                "Evaluation V2 is a measured baseline, not an enforced quality gate.",
                "Two supplied PDFs were scan-like and excluded because OCR is outside the frozen pipeline.",
                "Multi-evidence retrieval is materially weaker than document-level retrieval.",
                "pgvector 0.5.1 filtered ANN can return fewer candidates than the configured branch limit.",
            ]
        return EvaluationSummary(
            report_id=report["report_id"],
            dataset_sha256=self.frozen_sha256,
            aggregate=report["aggregate"],
            known_limitations=known_limitations,
        )

    def cases(self) -> list[EvaluationCaseView]:
        report = self._json(self.report_path)
        views = []
        for item in report["cases"]:
            raw = item.get("failure_attribution_v2", item.get("failure_attribution"))
            if raw == "INSUFFICIENT_EVIDENCE_FALSE_NEGATIVE":
                diagnosis = EvaluationDiagnosis.FALSE_ABSTENTION
            elif raw in {"OTHER", "MULTIPLE_AMBIGUOUS"}:
                diagnosis = EvaluationDiagnosis.AMBIGUOUS
            else:
                diagnosis = EvaluationDiagnosis(raw or "PASS")
            v2 = item.get("metrics_v2") or {}
            v2_retrieval = v2.get("retrieval_evidence")
            v2_context = v2.get("context_evidence")
            views.append(
                EvaluationCaseView(
                    case_id=item["case_id"],
                    category=item["category"],
                    question=item["question"],
                    answerable=item["answerable"],
                    retrieval_result=(
                        "COMPLETE" if v2_retrieval and v2_retrieval.get("complete")
                        else "PARTIAL" if v2_retrieval and v2_retrieval.get("partial")
                        else "MISS" if item["answerable"]
                        else "NOT_APPLICABLE"
                    ) if self.dataset_id == "legal_eval_v2" else (
                        "FOUND" if item["metrics"].get("retrieval_found") else (
                            "MISS" if item["answerable"] else "NOT_APPLICABLE"
                        )
                    ),
                    context_result=(
                        "COMPLETE" if v2_context and v2_context.get("complete")
                        else "PARTIAL" if v2_context and v2_context.get("partial")
                        else "NOT_RETAINED"
                    ) if self.dataset_id == "legal_eval_v2" and item["answerable"] else (
                        "RETAINED" if item["metrics"].get("context_retained") else (
                            "DROPPED" if item["metrics"].get("retrieved_but_dropped") else "NOT_RETAINED"
                        )
                    ),
                    generation_result=item["block6"]["status"],
                    diagnosis=diagnosis,
                )
            )
        return views

    def case_detail(self, case_id: str) -> EvaluationCaseDetail:
        dataset_case = self.dataset_case(case_id)
        report = self._json(self.report_path)
        measured = next((item for item in report["cases"] if item["case_id"] == case_id), None)
        if measured is None:
            raise KeyError(case_id)
        return EvaluationCaseDetail(
            dataset_case=dataset_case.model_dump(mode="json"),
            measured_case=measured,
        )

    def comparison(self) -> EvaluationComparison:
        if self.comparison_path is None:
            raise FileNotFoundError("Comparison artifact is not defined for Evaluation V2")
        report = self._json(self.comparison_path)

        def delta(before, after):
            result = {}
            for key in set(before) & set(after):
                left, right = before[key], after[key]
                if isinstance(left, dict) and isinstance(right, dict):
                    result[key] = delta(left, right)
                elif isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    result[key] = right - left
            return result

        return EvaluationComparison(
            before=report["before"],
            after=report["after"],
            delta=delta(report["before"], report["after"]),
            known_limitations=report.get("known_limitations", []),
        )


class DocumentObservabilityService:
    def __init__(self, db):
        self.db = db

    def list(self) -> list[DocumentPipelineView]:
        return [self._view(row) for row in self._rows()]

    def detail(self, document_id: str) -> DocumentDetailView:
        UUID(document_id)
        rows = self._rows(document_id)
        if not rows:
            raise KeyError(document_id)
        chunks = self.db.execute(
            text(
                """
                SELECT id, document_id, legal_unit_id, content_text, embedding_text,
                       metadata_json, provenance_json, page_start, page_end
                FROM chunks WHERE document_id = :document_id ORDER BY chunk_index
                """
            ),
            {"document_id": document_id},
        ).mappings().all()
        base = self._view(rows[0]).model_dump()
        return DocumentDetailView(
            **base,
            chunks=[
                ChunkDetail(
                    chunk_id=str(row["id"]),
                    document_id=str(row["document_id"]),
                    legal_unit_id=str(row["legal_unit_id"]) if row["legal_unit_id"] else None,
                    content_text=row["content_text"],
                    embedding_text=row["embedding_text"],
                    metadata_json=row["metadata_json"],
                    provenance_json=row["provenance_json"],
                    page_start=row["page_start"],
                    page_end=row["page_end"],
                )
                for row in chunks
            ],
        )

    def chunk(self, chunk_id: str) -> ChunkDetail:
        UUID(chunk_id)
        row = self.db.execute(
            text(
                """
                SELECT id, document_id, legal_unit_id, content_text, embedding_text,
                       metadata_json, provenance_json, page_start, page_end
                FROM chunks WHERE id = :chunk_id
                """
            ),
            {"chunk_id": chunk_id},
        ).mappings().one_or_none()
        if row is None:
            raise KeyError(chunk_id)
        return ChunkDetail(
            chunk_id=str(row["id"]),
            document_id=str(row["document_id"]),
            legal_unit_id=str(row["legal_unit_id"]) if row["legal_unit_id"] else None,
            content_text=row["content_text"],
            embedding_text=row["embedding_text"],
            metadata_json=row["metadata_json"],
            provenance_json=row["provenance_json"],
            page_start=row["page_start"],
            page_end=row["page_end"],
        )

    def _rows(self, document_id: str | None = None):
        where = "WHERE d.id = :document_id" if document_id else ""
        return self.db.execute(
            text(
                f"""
                SELECT d.id, d.filename, d.mime_type, d.file_size, d.status AS document_status,
                       d.created_at, d.updated_at,
                       ij.status AS ingestion_status, ij.current_stage AS ingestion_stage,
                       ij.error_stage AS ingestion_error_stage, ij.error_type AS ingestion_error_type,
                       ij.error_message AS ingestion_error_message,
                       pj.status AS processing_status, pj.current_stage AS processing_stage,
                       pj.error_stage AS processing_error_stage, pj.error_type AS processing_error_type,
                       pj.error_message AS processing_error_message,
                       xj.status AS indexing_status, xj.current_stage AS indexing_stage,
                       xj.error_stage AS indexing_error_stage, xj.error_type AS indexing_error_type,
                       xj.error_message AS indexing_error_message,
                       (SELECT count(*) FROM document_pages p WHERE p.document_id = d.id) AS page_count,
                       (SELECT count(*) FROM legal_units u WHERE u.document_id = d.id) AS legal_unit_count,
                       (SELECT count(*) FROM chunks c WHERE c.document_id = d.id) AS chunk_count,
                       (SELECT count(*) FROM chunk_indexes ci WHERE ci.document_id = d.id) AS index_count
                FROM documents d
                LEFT JOIN LATERAL (SELECT * FROM ingestion_jobs WHERE document_id=d.id ORDER BY created_at DESC LIMIT 1) ij ON true
                LEFT JOIN LATERAL (SELECT * FROM document_processing_jobs WHERE document_id=d.id ORDER BY started_at DESC NULLS LAST LIMIT 1) pj ON true
                LEFT JOIN LATERAL (SELECT * FROM indexing_jobs WHERE document_id=d.id ORDER BY created_at DESC LIMIT 1) xj ON true
                {where}
                ORDER BY d.created_at DESC
                """
            ),
            {"document_id": document_id} if document_id else {},
        ).mappings().all()

    @staticmethod
    def _stage(row, prefix, fallback):
        return PipelineStageSnapshot(
            status=row[f"{prefix}_status"] or fallback,
            current_stage=row[f"{prefix}_stage"],
            error_stage=row[f"{prefix}_error_stage"],
            error_type=row[f"{prefix}_error_type"],
            error_message=("The background operation failed safely." if row[f"{prefix}_error_message"] else None),
        )

    @classmethod
    def _view(cls, row):
        return DocumentPipelineView(
            document_id=str(row["id"]),
            filename=row["filename"],
            mime_type=row["mime_type"],
            file_size=row["file_size"],
            created_at=row["created_at"].isoformat() if row["created_at"] else None,
            updated_at=row["updated_at"].isoformat() if row["updated_at"] else None,
            ingestion=cls._stage(row, "ingestion", row["document_status"].value if hasattr(row["document_status"], "value") else str(row["document_status"])),
            processing=cls._stage(row, "processing", "NOT_STARTED"),
            indexing=cls._stage(row, "indexing", "NOT_STARTED"),
            page_count=row["page_count"],
            legal_unit_count=row["legal_unit_count"],
            chunk_count=row["chunk_count"],
            index_count=row["index_count"],
        )
