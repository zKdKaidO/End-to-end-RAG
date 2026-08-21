from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class DenseCandidate:
    chunk_id: UUID
    document_id: UUID
    dense_score: float
    dense_rank: int


@dataclass(frozen=True)
class LexicalCandidate:
    chunk_id: UUID
    document_id: UUID
    lexical_score: float
    lexical_rank: int


@dataclass(frozen=True)
class FusedCandidate:
    chunk_id: UUID
    document_id: UUID
    dense_score: float | None
    dense_rank: int | None
    lexical_score: float | None
    lexical_rank: int | None
    fusion_score: float
    final_rank: int


@dataclass(frozen=True)
class HydratedChunk:
    chunk_id: UUID
    document_id: UUID
    content_text: str
    metadata_json: dict[str, Any]
    provenance_json: dict[str, Any]
    legal_unit_id: UUID | None = None
