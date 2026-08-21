from types import SimpleNamespace

from evaluation.experiments.multi_evidence_v1.runner import (
    coverage_aware,
    expand_candidates,
    fuse_from_snapshot,
    piece_ranks,
)


def _candidate(chunk_id: str, rank: int, score: float = 0.8) -> dict:
    return {
        "chunk_id": chunk_id,
        "document_id": "doc-1",
        "dense_score": score,
        "dense_rank": rank,
    }


def test_snapshot_fusion_uses_frozen_rrf_and_stable_tie_break() -> None:
    report = {
        "block4": {
            "dense_candidates": [_candidate("b", 1), _candidate("a", 2)],
            "lexical_candidates": [
                {
                    "chunk_id": "a",
                    "document_id": "doc-1",
                    "lexical_score": 1.0,
                    "lexical_rank": 1,
                }
            ],
        }
    }

    ranked = fuse_from_snapshot(report)

    assert [item["chunk_id"] for item in ranked] == ["a", "b"]
    assert ranked[0]["fusion_score"] == 1 / 62 + 1 / 61
    assert [item["final_rank"] for item in ranked] == [1, 2]


def test_piece_ranks_handles_absent_branch_without_type_error() -> None:
    report = {
        "block4": {
            "dense_candidates": [],
            "lexical_candidates": [],
            "final_candidates": [],
        }
    }

    ranks = piece_ranks(report, [], "missing")

    assert ranks["dense_rank"] is None
    assert ranks["lexical_rank"] is None
    assert ranks["fusion_rank"] is None
    assert not any(value for key, value in ranks.items() if "top_" in key)


def test_hierarchy_expansion_is_bounded_and_deduplicated() -> None:
    graph = SimpleNamespace(
        chunks={
            "anchor": {"document_id": "doc-1", "content_text": "A", "metadata_json": {}, "provenance_json": {}},
            "child-1": {"document_id": "doc-1", "content_text": "B", "metadata_json": {}, "provenance_json": {}},
            "child-2": {"document_id": "doc-1", "content_text": "C", "metadata_json": {}, "provenance_json": {}},
        },
        related=lambda _chunk_id, _strategy: ["anchor", "child-1", "child-1", "child-2"],
    )
    anchor = {
        "chunk_id": "anchor",
        "document_id": "doc-1",
        "fusion_score": 0.1,
        "dense_score": 0.8,
        "dense_rank": 1,
        "lexical_score": None,
        "lexical_rank": None,
    }

    ranked, detail = expand_candidates([anchor], graph, "CHILDREN", per_anchor=2, total_limit=3)

    assert [item["chunk_id"] for item in ranked] == ["anchor", "child-1"]
    assert detail["new_candidate_count"] == 1


def test_coverage_selection_prefers_new_legal_units() -> None:
    graph = SimpleNamespace(
        unit_id=lambda chunk_id: {"a": "u1", "b": "u1", "c": "u2"}[chunk_id],
        article_id=lambda chunk_id: {"a": "article-1", "b": "article-1", "c": "article-2"}[chunk_id],
    )
    pool = [
        {"chunk_id": "a", "fusion_score": 0.3},
        {"chunk_id": "b", "fusion_score": 0.2},
        {"chunk_id": "c", "fusion_score": 0.1},
    ]

    selected = coverage_aware(pool, graph, top_k=2)

    assert [item["chunk_id"] for item in selected] == ["a", "c"]

