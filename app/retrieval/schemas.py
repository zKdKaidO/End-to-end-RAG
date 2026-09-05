import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.retrieval.hierarchy_types import CandidateOrigin, HierarchyRelation


class RetrievalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_text: str
    top_k_dense: int | None = None
    top_k_lexical: int | None = None
    top_k_final: int | None = None
    rrf_k: int | None = None
    document_ids: list[str] | None = None

    @model_validator(mode="before")
    @classmethod
    def resolve_server_defaults(cls, value):
        if not isinstance(value, dict):
            return value
        # This executes only while a request is being validated.  Normal API
        # behavior remains configuration-driven; importing the result model is
        # now safe for the local desktop runtime.
        from app.core.config import settings

        data = dict(value)
        defaults = {
            "top_k_dense": settings.RETRIEVAL_TOP_K_DENSE_DEFAULT,
            "top_k_lexical": settings.RETRIEVAL_TOP_K_LEXICAL_DEFAULT,
            "top_k_final": settings.RETRIEVAL_TOP_K_FINAL_DEFAULT,
            "rrf_k": settings.RETRIEVAL_RRF_K_DEFAULT,
        }
        for field_name, default in defaults.items():
            if data.get(field_name) is None:
                data[field_name] = default
        if len(str(data.get("query_text", ""))) > settings.REQUEST_MAX_QUERY_CHARS:
            raise ValueError(
                f"query_text exceeds the safety limit of {settings.REQUEST_MAX_QUERY_CHARS}"
            )
        return data


class HierarchyAnchorReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    anchor_chunk_id: str
    anchor_legal_unit_id: str
    anchor_retrieval_final_rank: int = Field(gt=0, le=10)


class RetrievedCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str
    document_id: str
    content_text: str
    metadata_json: dict[str, Any]
    provenance_json: dict[str, Any]
    dense_score: float | None
    dense_rank: int | None
    lexical_score: float | None
    lexical_rank: int | None
    fusion_score: float | None

    retrieval_final_rank: int | None = Field(default=None, gt=0, le=10)
    context_candidate_order: int = Field(gt=0)
    candidate_origin: CandidateOrigin = CandidateOrigin.RETRIEVAL
    legal_unit_id: str | None = None
    hierarchy_relation: HierarchyRelation | None = None
    hierarchy_depth: Literal[0, 1] = 0
    anchor_chunk_id: str | None = None
    anchor_legal_unit_id: str | None = None
    anchor_retrieval_final_rank: int | None = Field(default=None, gt=0, le=10)
    hierarchy_anchor_references: list[HierarchyAnchorReference] = Field(default_factory=list)

    # Temporary response compatibility alias. This remains the immutable RRF
    # rank for retrieval candidates and is always null for hierarchy children.
    final_rank: int | None = Field(default=None, gt=0, le=10)

    @model_validator(mode="before")
    @classmethod
    def adapt_frozen_candidate(cls, value):
        if not isinstance(value, dict):
            return value
        data = dict(value)
        if data.get("retrieval_final_rank") is None and data.get("final_rank") is not None:
            data["retrieval_final_rank"] = data["final_rank"]
        if data.get("final_rank") is None and data.get("retrieval_final_rank") is not None:
            data["final_rank"] = data["retrieval_final_rank"]
        if data.get("context_candidate_order") is None:
            rank = data.get("retrieval_final_rank")
            if rank is not None:
                data["context_candidate_order"] = rank
        return data

    @model_validator(mode="after")
    def validate_origin_contract(self):
        if self.candidate_origin == CandidateOrigin.RETRIEVAL:
            if self.retrieval_final_rank is None or self.final_rank != self.retrieval_final_rank:
                raise ValueError("retrieval candidates require one immutable RRF rank")
            if self.dense_rank is None and self.lexical_rank is None:
                raise ValueError("retrieval candidates require a branch rank")
            if self.fusion_score is None or not math.isfinite(self.fusion_score):
                raise ValueError("retrieval candidates require a finite fusion score")
            if self.hierarchy_depth != 0 or self.hierarchy_relation is not None:
                raise ValueError("retrieval candidates cannot claim a hierarchy relation")
            if any(
                value is not None
                for value in (
                    self.anchor_chunk_id,
                    self.anchor_legal_unit_id,
                    self.anchor_retrieval_final_rank,
                )
            ):
                raise ValueError("retrieval candidates cannot claim a hierarchy anchor")
            return self

        retrieval_signals = (
            self.retrieval_final_rank,
            self.final_rank,
            self.dense_score,
            self.dense_rank,
            self.lexical_score,
            self.lexical_rank,
            self.fusion_score,
        )
        if any(value is not None for value in retrieval_signals):
            raise ValueError("hierarchy children cannot have retrieval scores or ranks")
        if self.hierarchy_relation != HierarchyRelation.DIRECT_CHILD or self.hierarchy_depth != 1:
            raise ValueError("hierarchy children must be one-hop DIRECT_CHILD candidates")
        if not all(
            (
                self.legal_unit_id,
                self.anchor_chunk_id,
                self.anchor_legal_unit_id,
                self.anchor_retrieval_final_rank,
                self.hierarchy_anchor_references,
            )
        ):
            raise ValueError("hierarchy children require authoritative anchor fields")
        primary = self.hierarchy_anchor_references[0]
        if (
            primary.anchor_chunk_id != self.anchor_chunk_id
            or primary.anchor_legal_unit_id != self.anchor_legal_unit_id
            or primary.anchor_retrieval_final_rank != self.anchor_retrieval_final_rank
        ):
            raise ValueError("primary hierarchy anchor must equal the first anchor reference")
        return self


class RetrievalResponse(BaseModel):
    results: list[RetrievedCandidate]
