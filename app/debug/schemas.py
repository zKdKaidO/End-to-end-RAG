from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DebugRagRequest(StrictModel):
    query_text: str = Field(min_length=1, max_length=20_000)
    document_ids: list[str] | None = None
    evaluation_case_id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9_-]*$")

    @field_validator("query_text")
    @classmethod
    def reject_blank_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query_text must not be empty or whitespace-only")
        return value.strip()


class LexicalMode(str, Enum):
    STRICT_MATCH = "STRICT_MATCH"
    SELECTIVE_FALLBACK = "SELECTIVE_FALLBACK"
    NO_LEXICAL_MATCH = "NO_LEXICAL_MATCH"


class EvaluationDiagnosis(str, Enum):
    PASS = "PASS"
    RETRIEVAL_MISS = "RETRIEVAL_MISS"
    WRONG_DOCUMENT = "WRONG_DOCUMENT"
    PARTIAL_MULTI_EVIDENCE_RETRIEVAL = "PARTIAL_MULTI_EVIDENCE_RETRIEVAL"
    CONTEXT_DROP = "CONTEXT_DROP"
    GENERATION_MISSING_CITATION = "GENERATION_MISSING_CITATION"
    GENERATION_INVALID_CITATION = "GENERATION_INVALID_CITATION"
    GENERATION_WRONG_SOURCE = "GENERATION_WRONG_SOURCE"
    UNSUPPORTED_ANSWER = "UNSUPPORTED_ANSWER"
    FALSE_ABSTENTION = "FALSE_ABSTENTION"
    AMBIGUOUS = "AMBIGUOUS"


class CandidateSnapshot(StrictModel):
    chunk_id: str
    document_id: str
    dense_rank: int | None = None
    dense_score: float | None = None
    lexical_rank: int | None = None
    lexical_score: float | None = None
    fusion_score: float | None = None
    final_rank: int | None = None
    retrieval_final_rank: int | None = None
    context_candidate_order: int | None = None
    candidate_origin: str | None = None
    legal_unit_id: str | None = None
    hierarchy_relation: str | None = None
    hierarchy_depth: int | None = None
    anchor_chunk_id: str | None = None
    anchor_legal_unit_id: str | None = None
    anchor_retrieval_final_rank: int | None = None
    hierarchy_anchor_references: list[dict[str, Any]] = Field(default_factory=list)
    content_preview: str
    content_text: str | None = None
    metadata_json: dict[str, Any] | None = None
    provenance_json: dict[str, Any] | None = None


class RetrievalSnapshot(StrictModel):
    dense_candidates: list[CandidateSnapshot]
    lexical_candidates: list[CandidateSnapshot]
    final_candidates: list[CandidateSnapshot]
    rrf_candidates: list[CandidateSnapshot] = Field(default_factory=list)
    hierarchy_candidates: list[CandidateSnapshot] = Field(default_factory=list)
    final_context_candidates: list[CandidateSnapshot] = Field(default_factory=list)
    hierarchy: dict[str, Any] = Field(default_factory=dict)
    dense_candidate_count: int = Field(ge=0)
    lexical_candidate_count: int = Field(ge=0)
    overlap_count: int = Field(ge=0)
    lexical_mode: LexicalMode
    score_semantics: str = "DIAGNOSTIC_RANKING_SIGNALS_NOT_CALIBRATED_CONFIDENCE"
    timings_ms: dict[str, float]


class SelectedEvidenceSnapshot(StrictModel):
    source_id: str
    retrieval_final_rank: int | None
    context_candidate_order: int
    candidate_origin: str
    legal_unit_id: str | None
    hierarchy_relation: str | None
    hierarchy_depth: int
    anchor_chunk_id: str | None
    anchor_legal_unit_id: str | None
    anchor_retrieval_final_rank: int | None
    chunk_id: str
    document_id: str
    token_count: int
    content_text: str
    metadata_json: dict[str, Any]
    provenance_json: dict[str, Any]
    dense_rank: int | None
    lexical_rank: int | None
    fusion_score: float | None


class ContextSnapshot(StrictModel):
    candidate_count: int
    duplicate_count: int
    selected_count: int
    dropped_count: int
    context_token_count: int
    context_budget_tokens: int
    budget_utilization_percent: float
    budget_exhausted: bool
    stop_reason: str
    selected_evidence: list[SelectedEvidenceSnapshot]


class CitationSnapshot(StrictModel):
    source_id: str
    chunk_id: str
    document_id: str
    metadata_json: dict[str, Any]
    provenance_json: dict[str, Any]
    retrieval_final_rank: int | None = None


class GenerationSnapshot(StrictModel):
    status: str
    answerability_status: str | None
    answerability_validation: str
    answer_text: str
    citations: list[CitationSnapshot]
    invalid_citations: list[str]
    citation_validation: str
    model_id: str
    prompt_version: str
    finish_reason: str | None
    usage: dict[str, Any] | None
    prompt_token_count: int
    context_token_count: int
    generation_ms: float | None
    time_to_first_token_ms: float | None


class EvaluationExpectedSnapshot(StrictModel):
    case_id: str
    category: str
    answerable: bool
    expected_document_ids: list[str]
    acceptable_evidence_sets: list[list[str]]
    source_reference: str | None
    notes: str | None


class DebugTrace(StrictModel):
    request_id: str
    query_text: str
    document_ids: list[str]
    retrieval: RetrievalSnapshot
    context: ContextSnapshot
    generation: GenerationSnapshot
    timings_ms: dict[str, float]
    expected: EvaluationExpectedSnapshot | None = None
    diagnosis: EvaluationDiagnosis | None = None


class ChunkDetail(StrictModel):
    chunk_id: str
    document_id: str
    legal_unit_id: str | None
    content_text: str
    embedding_text: str
    metadata_json: dict[str, Any]
    provenance_json: dict[str, Any]
    page_start: int
    page_end: int


class EvaluationSummary(StrictModel):
    report_id: str
    dataset_sha256: str
    aggregate: dict[str, Any]
    known_limitations: list[str]


class EvaluationCaseView(StrictModel):
    case_id: str
    category: str
    question: str
    answerable: bool
    retrieval_result: str
    context_result: str
    generation_result: str
    diagnosis: EvaluationDiagnosis


class EvaluationCaseDetail(StrictModel):
    dataset_case: dict[str, Any]
    measured_case: dict[str, Any]


class EvaluationComparison(StrictModel):
    before: dict[str, Any]
    after: dict[str, Any]
    delta: dict[str, Any]
    known_limitations: list[str]


class PipelineStageSnapshot(StrictModel):
    status: str
    current_stage: str | None = None
    error_stage: str | None = None
    error_type: str | None = None
    error_message: str | None = None


class DocumentPipelineView(StrictModel):
    document_id: str
    filename: str
    mime_type: str
    file_size: int
    created_at: str | None
    updated_at: str | None
    ingestion: PipelineStageSnapshot
    processing: PipelineStageSnapshot
    indexing: PipelineStageSnapshot
    page_count: int
    legal_unit_count: int
    chunk_count: int
    index_count: int


class DocumentDetailView(DocumentPipelineView):
    chunks: list[ChunkDetail]
