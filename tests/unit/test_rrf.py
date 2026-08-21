from uuid import UUID

import pytest

from app.retrieval.rrf import reciprocal_rank_fusion
from app.retrieval.types import DenseCandidate, LexicalCandidate


DOC = UUID("00000000-0000-0000-0000-000000000099")


def dense(number, rank, score=0.5):
    return DenseCandidate(UUID(int=number), DOC, score, rank)


def lexical(number, rank, score=0.25):
    return LexicalCandidate(UUID(int=number), DOC, score, rank)


def test_rrf_exact_arithmetic_and_overlap():
    result = reciprocal_rank_fusion([dense(1, 1)], [lexical(1, 2)], 60, 10)
    assert len(result) == 1
    assert result[0].fusion_score == pytest.approx(1 / 61 + 1 / 62)
    assert result[0].dense_rank == 1
    assert result[0].lexical_rank == 2
    assert result[0].final_rank == 1


def test_dense_only_and_lexical_only_nullable_fields():
    result = reciprocal_rank_fusion([dense(1, 1)], [lexical(2, 1)], 60, 10)
    assert {item.chunk_id for item in result} == {UUID(int=1), UUID(int=2)}
    by_id = {item.chunk_id: item for item in result}
    assert by_id[UUID(int=1)].lexical_rank is None
    assert by_id[UUID(int=2)].dense_rank is None


@pytest.mark.parametrize(
    "dense_list,lexical_list,expected",
    [
        ([], [], []),
        ([], [lexical(1, 1)], [UUID(int=1)]),
        ([dense(1, 1)], [], [UUID(int=1)]),
        ([dense(2, 1)], [lexical(1, 1)], [UUID(int=1), UUID(int=2)]),
    ],
)
def test_empty_and_disjoint_branches(dense_list, lexical_list, expected):
    result = reciprocal_rank_fusion(dense_list, lexical_list, 60, 10)
    assert [item.chunk_id for item in result] == expected


def test_rrf_k_is_configurable():
    low_k = reciprocal_rank_fusion([dense(1, 2)], [], 1, 10)[0]
    high_k = reciprocal_rank_fusion([dense(1, 2)], [], 100, 10)[0]
    assert low_k.fusion_score == pytest.approx(1 / 3)
    assert high_k.fusion_score == pytest.approx(1 / 102)


def test_deterministic_chunk_id_tie_break():
    result = reciprocal_rank_fusion([dense(2, 1), dense(1, 1)], [], 60, 10)
    assert [item.chunk_id for item in result] == [UUID(int=1), UUID(int=2)]


def test_top_k_final_is_honored_and_rank_is_one_based():
    result = reciprocal_rank_fusion(
        [dense(1, 1), dense(2, 2), dense(3, 3)], [], 60, 2
    )
    assert len(result) == 2
    assert [item.final_rank for item in result] == [1, 2]


@pytest.mark.parametrize(
    "dense_list,lexical_list,error",
    [([dense(1, 0)], [], "dense ranks"), ([], [lexical(1, 0)], "lexical ranks")],
)
def test_branch_rank_must_start_at_one(dense_list, lexical_list, error):
    with pytest.raises(ValueError, match=error):
        reciprocal_rank_fusion(dense_list, lexical_list, 60, 10)
