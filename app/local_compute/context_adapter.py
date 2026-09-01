"""Thin local-result adapter for the frozen deterministic Block 5 builder."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.context.service import ContextBuilderService
from app.retrieval.schemas import RetrievedCandidate


_CANDIDATE_FIELDS = frozenset(RetrievedCandidate.model_fields)


def local_candidates_to_retrieved(
    local_results: Sequence[dict[str, Any]],
) -> list[RetrievedCandidate]:
    """Drop local transport-only fields and validate the canonical contract."""

    return [
        RetrievedCandidate.model_validate(
            {key: value for key, value in result.items() if key in _CANDIDATE_FIELDS}
        )
        for result in local_results
    ]


def build_local_context(
    *,
    request_id: str,
    query_text: str,
    local_results: Sequence[dict[str, Any]],
    context_budget_tokens: int,
    context_builder: ContextBuilderService,
):
    """Use the existing Block 5 implementation; this adapter owns no policy."""

    return context_builder.build(
        request_id=request_id,
        query_text=query_text,
        retrieved_candidates=local_candidates_to_retrieved(local_results),
        context_budget_tokens=context_budget_tokens,
    )
