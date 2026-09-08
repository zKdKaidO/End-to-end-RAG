"""Bounded, deterministic query planning for local legal retrieval.

The fast path deliberately avoids a model call. It retains the original user
query in every plan and adds at most three purpose-specific retrieval queries.
No document text is ever supplied to this planner.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum


class QueryKind(str, Enum):
    DIRECT = "DIRECT"
    MULTI_INTENT = "MULTI_INTENT"
    MULTI_HOP = "MULTI_HOP"
    NUMERIC = "NUMERIC"


@dataclass(frozen=True)
class QueryPlan:
    query_kind: QueryKind
    retrieval_queries: tuple[str, ...]
    information_needs: tuple[str, ...]
    planner_used: bool = False

    def __post_init__(self) -> None:
        if not self.retrieval_queries or len(self.retrieval_queries) > 4:
            raise ValueError("QueryPlan must have one to four retrieval queries")
        if self.retrieval_queries[0] != self.information_needs[0]:
            raise ValueError("QueryPlan must retain the original query first")


_NUMERIC = re.compile(
    r"(?:tổng|bao nhiêu|%|phần trăm|tính|cộng|trừ|nhân|chia|tỷ lệ|giờ tín chỉ)",
    re.IGNORECASE,
)
_MULTI = re.compile(
    r"(?:\bvà\b|\blần lượt\b|\bphân nhóm\b|\btổng hợp\b|\bso sánh\b|\bcả hai\b)",
    re.IGNORECASE,
)


def plan_query(query_text: str) -> QueryPlan:
    """Return a bounded fast-path plan; ambiguous text remains original-only."""
    if not isinstance(query_text, str) or not query_text.strip():
        raise ValueError("query_text must not be empty")
    original = unicodedata.normalize("NFC", query_text).strip()
    numeric = bool(_NUMERIC.search(original))
    multi = bool(_MULTI.search(original))
    kind = QueryKind.NUMERIC if numeric else QueryKind.MULTI_INTENT if multi else QueryKind.DIRECT
    queries = [original]
    if kind is not QueryKind.DIRECT:
        # Clause fragments are supplemental retrieval cues, never a rewrite
        # of intent. Short scaffolding fragments are ignored.
        fragments = re.split(r"(?:\?|;|\bvà\b|\bđồng thời\b)", original, flags=re.IGNORECASE)
        for fragment in fragments:
            normalized = fragment.strip(" .,:-–—")
            if len(normalized) >= 12 and normalized not in queries:
                queries.append(normalized)
            if len(queries) == 4:
                break
    return QueryPlan(kind, tuple(queries), tuple(queries))
