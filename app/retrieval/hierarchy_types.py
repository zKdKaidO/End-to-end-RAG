from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID


class CandidateOrigin(str, Enum):
    RETRIEVAL = "RETRIEVAL"
    HIERARCHY_CHILD = "HIERARCHY_CHILD"


class HierarchyRelation(str, Enum):
    DIRECT_CHILD = "DIRECT_CHILD"


class HierarchyExpansionStatus(str, Enum):
    DISABLED = "DISABLED"
    EXPANDED = "EXPANDED"
    NO_EXPANSION = "NO_EXPANSION"
    BASELINE_FALLBACK = "BASELINE_FALLBACK"


@dataclass(frozen=True)
class DirectChildRow:
    anchor_chunk_id: UUID
    anchor_legal_unit_id: UUID
    child_legal_unit_id: UUID
    document_id: UUID
    child_char_start: int
    child_unit_type: str
    child_unit_number: str | None
    child_unit_title: str | None
    child_chunk_id: UUID
    child_chunk_index: int
    content_text: str
    metadata_json: dict[str, Any]
    provenance_json: dict[str, Any]


@dataclass
class HierarchyExpansionDiagnostics:
    status: HierarchyExpansionStatus
    enabled: bool
    stage: str | None = None
    reason_codes: list[str] = field(default_factory=list)
    base_anchor_count: int = 0
    unique_anchor_unit_count: int = 0
    anchors_expanded: int = 0
    anchors_without_legal_unit: int = 0
    anchors_without_children: int = 0
    children_examined: int = 0
    children_added: int = 0
    duplicates_rejected: int = 0
    document_filter_rejections: int = 0
    per_anchor_cap_hits: int = 0
    global_cap_reached: bool = False
    fallback_used: bool = False
    hierarchy_lookup_ms: float = 0.0
    hierarchy_total_ms: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.__dict__,
            "status": self.status.value,
        }

