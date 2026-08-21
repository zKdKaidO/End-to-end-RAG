from uuid import UUID

import pytest

from app.retrieval.hierarchy_expander import LegalHierarchyExpander
from app.retrieval.hierarchy_types import (
    CandidateOrigin,
    DirectChildRow,
    HierarchyExpansionStatus,
)
from app.retrieval.schemas import RetrievedCandidate


DOC = UUID(int=10_000)
OTHER_DOC = UUID(int=20_000)


def base(rank: int, *, unit: int | None = None, chunk: int | None = None):
    chunk_id = UUID(int=chunk or rank)
    return RetrievedCandidate(
        chunk_id=str(chunk_id),
        document_id=str(DOC),
        content_text=f"anchor {rank}",
        metadata_json={"rank": rank},
        provenance_json={"page": rank},
        dense_score=0.9 - rank / 100,
        dense_rank=rank,
        lexical_score=None,
        lexical_rank=None,
        fusion_score=1 / (60 + rank),
        retrieval_final_rank=rank,
        final_rank=rank,
        context_candidate_order=rank,
        candidate_origin=CandidateOrigin.RETRIEVAL,
        legal_unit_id=str(UUID(int=unit)) if unit is not None else None,
    )


def child(anchor_rank: int, child_number: int, *, document=DOC, anchor_unit=None):
    anchor_unit = anchor_unit or (100 + anchor_rank)
    return DirectChildRow(
        anchor_chunk_id=UUID(int=anchor_rank),
        anchor_legal_unit_id=UUID(int=anchor_unit),
        child_legal_unit_id=UUID(int=1_000 + child_number),
        document_id=document,
        child_char_start=child_number * 10,
        child_unit_type="CLAUSE",
        child_unit_number=str(child_number),
        child_unit_title=None,
        child_chunk_id=UUID(int=10_000 + child_number),
        child_chunk_index=child_number,
        content_text=f"child {child_number}",
        metadata_json={"child": child_number},
        provenance_json={"page": child_number},
    )


class RowsRepository:
    def __init__(self, rows=(), error=None):
        self.rows = list(rows)
        self.error = error
        self.calls = []

    def lookup_direct_children(self, anchor_chunk_ids, document_ids):
        self.calls.append((list(anchor_chunk_ids), list(document_ids)))
        if self.error:
            raise self.error
        return list(self.rows)


def expander(repository, enabled=True):
    return LegalHierarchyExpander(
        repository,
        enabled=enabled,
        max_anchors=10,
        max_children_per_anchor=4,
        max_candidates_added=20,
        depth=1,
    )


def expand(anchors, rows=(), *, document_ids=(), enabled=True, error=None):
    repository = RowsRepository(rows, error)
    result, diagnostics = expander(repository, enabled).expand(
        anchors, document_ids, canonical_anchor_window=True
    )
    return result, diagnostics, repository


def test_no_legal_unit_and_no_children_keep_anchors_without_expansion():
    result, diagnostic, repository = expand([base(1)])
    assert [item.chunk_id for item in result] == [str(UUID(int=1))]
    assert repository.calls == []
    assert diagnostic.status == HierarchyExpansionStatus.NO_EXPANSION
    assert diagnostic.anchors_without_legal_unit == 1

    result, diagnostic, repository = expand([base(1, unit=101)])
    assert len(repository.calls) == 1
    assert len(result) == 1
    assert diagnostic.anchors_without_children == 1


def test_direct_children_are_one_hop_structural_candidates_with_real_provenance():
    anchors = [base(1, unit=101)]
    result, diagnostic, _ = expand(anchors, [child(1, 1), child(1, 2)])
    assert [item.content_text for item in result] == ["anchor 1", "child 1", "child 2"]
    added = result[1:]
    assert all(item.candidate_origin == CandidateOrigin.HIERARCHY_CHILD for item in added)
    assert all(item.hierarchy_depth == 1 for item in added)
    assert all(item.hierarchy_relation.value == "DIRECT_CHILD" for item in added)
    assert all(item.retrieval_final_rank is None and item.final_rank is None for item in added)
    assert all(item.dense_score is None and item.lexical_score is None for item in added)
    assert all(item.fusion_score is None for item in added)
    assert added[0].metadata_json == {"child": 1}
    assert added[0].provenance_json == {"page": 1}
    assert diagnostic.children_added == 2


def test_per_anchor_and_global_caps_preserve_all_base_anchors():
    anchors = [base(rank, unit=100 + rank) for rank in range(1, 7)]
    rows = [
        child(rank, rank * 100 + offset)
        for rank in range(1, 7)
        for offset in range(1, 6)
    ]
    result, diagnostic, _ = expand(anchors, rows)
    added = [item for item in result if item.candidate_origin == CandidateOrigin.HIERARCHY_CHILD]
    assert len(added) == 20
    assert len(result) == 26
    assert {item.chunk_id for item in anchors}.issubset({item.chunk_id for item in result})
    assert diagnostic.per_anchor_cap_hits >= 4
    assert diagnostic.global_cap_reached is True
    assert "PER_ANCHOR_CAP_REACHED" in diagnostic.reason_codes
    assert "GLOBAL_CAP_REACHED" in diagnostic.reason_codes


def test_base_wins_duplicate_and_retrieval_rank_is_immutable():
    duplicate_id = 10_001
    anchors = [base(1, unit=101), base(2, unit=102, chunk=duplicate_id)]
    result, diagnostic, _ = expand(anchors, [child(1, 1)])
    assert len(result) == 2
    duplicate = next(item for item in result if item.chunk_id == str(UUID(int=duplicate_id)))
    assert duplicate.candidate_origin == CandidateOrigin.RETRIEVAL
    assert duplicate.retrieval_final_rank == 2
    assert duplicate.dense_rank == 2
    assert diagnostic.duplicates_rejected == 1


def test_duplicate_anchor_unit_collapses_lookup_and_retains_references():
    anchors = [base(1, unit=101), base(2, unit=101)]
    result, diagnostic, repository = expand(anchors, [child(1, 1)])
    assert repository.calls[0][0] == [UUID(int=1)]
    added = next(item for item in result if item.candidate_origin == CandidateOrigin.HIERARCHY_CHILD)
    assert [ref.anchor_retrieval_final_rank for ref in added.hierarchy_anchor_references] == [1, 2]
    assert diagnostic.unique_anchor_unit_count == 1


def test_same_child_from_multiple_anchors_is_emitted_once_with_stable_primary():
    anchors = [base(1, unit=101), base(2, unit=102)]
    rows = [child(2, 1, anchor_unit=102), child(1, 1, anchor_unit=101)]
    result, diagnostic, _ = expand(anchors, rows)
    added = [item for item in result if item.candidate_origin == CandidateOrigin.HIERARCHY_CHILD]
    assert len(added) == 1
    assert added[0].anchor_retrieval_final_rank == 1
    assert [ref.anchor_retrieval_final_rank for ref in added[0].hierarchy_anchor_references] == [1, 2]
    assert diagnostic.duplicates_rejected == 1


def test_document_filter_is_defensively_enforced_and_mismatch_falls_back():
    anchors = [base(1, unit=101)]
    result, diagnostic, repository = expand(
        anchors, [child(1, 1, document=OTHER_DOC)], document_ids=[DOC]
    )
    # A stored cross-document parent relation is an invariant failure, so the
    # atomic enrichment result is discarded rather than partially emitted.
    assert len(result) == 1
    assert diagnostic.status == HierarchyExpansionStatus.BASELINE_FALLBACK
    assert diagnostic.fallback_used is True
    assert repository.calls[0][1] == [DOC]


def test_order_is_anchor_then_source_ordered_children_then_next_anchor():
    anchors = [base(2, unit=102), base(1, unit=101)]
    rows = [child(1, 3), child(2, 4), child(1, 1), child(1, 2)]
    result, _, _ = expand(anchors, rows)
    assert [item.content_text for item in result] == [
        "anchor 1", "child 3", "child 1", "child 2", "anchor 2", "child 4"
    ]
    # The repository owns legal-source ordering. The expander preserves its
    # returned per-anchor order and assigns a gapless context order.
    assert [item.context_candidate_order for item in result] == list(range(1, 7))
    assert [item.retrieval_final_rank for item in result if item.candidate_origin == CandidateOrigin.RETRIEVAL] == [1, 2]


def test_lookup_failure_is_atomic_baseline_fallback():
    anchors = [base(1, unit=101), base(2, unit=102)]
    result, diagnostic, _ = expand(anchors, error=RuntimeError("fault injection"))
    assert [item.chunk_id for item in result] == [item.chunk_id for item in anchors]
    assert diagnostic.status == HierarchyExpansionStatus.BASELINE_FALLBACK
    assert diagnostic.fallback_used is True
    assert diagnostic.children_added == 0


def test_disabled_or_noncanonical_window_does_no_lookup():
    anchors = [base(1, unit=101)]
    result, diagnostic, repository = expand(anchors, [child(1, 1)], enabled=False)
    assert len(result) == 1
    assert repository.calls == []
    assert diagnostic.status == HierarchyExpansionStatus.DISABLED

    repository = RowsRepository([child(1, 1)])
    result, diagnostic = expander(repository).expand(
        anchors, (), canonical_anchor_window=False
    )
    assert len(result) == 1
    assert repository.calls == []
    assert diagnostic.status == HierarchyExpansionStatus.DISABLED


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_anchors": 9},
        {"max_children_per_anchor": 5},
        {"max_candidates_added": 21},
        {"depth": 2},
    ],
)
def test_server_owned_bounds_are_frozen(kwargs):
    values = dict(
        enabled=True,
        max_anchors=10,
        max_children_per_anchor=4,
        max_candidates_added=20,
        depth=1,
    )
    values.update(kwargs)
    with pytest.raises(ValueError):
        LegalHierarchyExpander(RowsRepository(), **values)
