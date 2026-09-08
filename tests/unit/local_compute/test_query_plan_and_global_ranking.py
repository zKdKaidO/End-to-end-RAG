from __future__ import annotations

from app.local_compute.query_plan import QueryKind, plan_query
from app.local_compute.retrieval import _ArtifactRow, _LexicalHit, LocalRetrievalStore


def _row(chunk_id: str, document_id: str) -> _ArtifactRow:
    return _ArtifactRow(
        chunk_id, document_id, None, "x", "{}", "{}", b"", 768, 1, "block3-v1", ()
    )


def test_dense_rank_is_global_across_document_artifacts():
    stronger = _row("a", "doc-a")
    irrelevant_local_winner = _row("b", "doc-b")
    ranks = LocalRetrievalStore._global_dense_ranks(
        [(0.93, stronger), (0.11, irrelevant_local_winner)], 50
    )
    assert ranks["a"][1] == 1
    assert ranks["b"][1] == 2


def test_lexical_rank_is_one_global_order_not_per_document_rank_one():
    ranks, scores = LocalRetrievalStore._global_lexical_ranks(
        [
            [_LexicalHit("a", "doc-a", -10.0, 1, 1.0)],
            [_LexicalHit("b", "doc-b", -1.0, 1, 1.0)],
        ]
    )
    assert set(ranks.values()) == {1, 2}
    assert scores == {"a": 1.0, "b": 1.0}


def test_numeric_multi_plan_keeps_original_and_is_bounded():
    query = "Tính tổng giờ của A và B, lần lượt theo các hình thức nào?"
    plan = plan_query(query)
    assert plan.query_kind is QueryKind.NUMERIC
    assert plan.retrieval_queries[0] == query
    assert 1 <= len(plan.retrieval_queries) <= 4


def test_direct_plan_uses_only_original_query():
    query = "Điều kiện áp dụng là gì?"
    plan = plan_query(query)
    assert plan.query_kind is QueryKind.DIRECT
    assert plan.retrieval_queries == (query,)
