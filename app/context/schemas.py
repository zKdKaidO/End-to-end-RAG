from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.retrieval.hierarchy_types import CandidateOrigin, HierarchyRelation
from app.retrieval.schemas import HierarchyAnchorReference


class StopReason(str, Enum):
    NONE = "NONE"
    TOKEN_BUDGET = "TOKEN_BUDGET"
    TOP_EVIDENCE_EXCEEDS_CONTEXT_BUDGET = "TOP_EVIDENCE_EXCEEDS_CONTEXT_BUDGET"


class SelectedEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^S[1-9][0-9]*$")
    chunk_id: str
    document_id: str
    content_text: str
    metadata_json: dict[str, Any]
    provenance_json: dict[str, Any]
    retrieval_final_rank: int | None = Field(default=None, gt=0)
    context_candidate_order: int = Field(gt=0)
    candidate_origin: CandidateOrigin = CandidateOrigin.RETRIEVAL
    legal_unit_id: str | None = None
    hierarchy_relation: HierarchyRelation | None = None
    hierarchy_depth: int = Field(default=0, ge=0, le=1)
    anchor_chunk_id: str | None = None
    anchor_legal_unit_id: str | None = None
    anchor_retrieval_final_rank: int | None = Field(default=None, gt=0, le=10)
    hierarchy_anchor_references: list[HierarchyAnchorReference] = Field(default_factory=list)
    dense_score: float | None
    dense_rank: int | None
    lexical_score: float | None
    lexical_rank: int | None
    fusion_score: float | None
    token_count: int = Field(ge=0)

    @model_validator(mode="before")
    @classmethod
    def adapt_frozen_selected_evidence(cls, value):
        if isinstance(value, dict) and value.get("context_candidate_order") is None:
            data = dict(value)
            data["context_candidate_order"] = data.get("retrieval_final_rank")
            return data
        return value


class ContextPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    query_text: str
    context_text: str
    selected_evidence: list[SelectedEvidence]
    context_token_count: int = Field(ge=0)
    context_budget_tokens: int = Field(gt=0)
    candidate_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    selected_count: int = Field(ge=0)
    dropped_count: int = Field(ge=0)
    budget_exhausted: bool
    stop_reason: StopReason
