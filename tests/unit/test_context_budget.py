from uuid import UUID

import pytest

from app.context.formatter import EVIDENCE_SEPARATOR, format_evidence_block
from app.context.schemas import StopReason
from app.context.service import ContextBuilderService
from app.retrieval.schemas import RetrievedCandidate
from tests.context_doubles import CharacterTokenCounter


DOC = "00000000-0000-0000-0000-000000000010"


def candidate(number, rank, text=None, document_id=DOC):
    return RetrievedCandidate(
        chunk_id=str(UUID(int=number)),
        document_id=document_id,
        content_text=text or f"Nội dung pháp lý {number}.",
        metadata_json={
            "document_type": "Nghị định",
            "document_number": "135/2026/NĐ-CP",
            "title": "Quy định chính sách",
        },
        provenance_json={"page_start": rank, "page_end": rank},
        dense_score=0.9 - rank / 100,
        dense_rank=rank,
        lexical_score=None,
        lexical_rank=None,
        fusion_score=1 / (60 + rank),
        final_rank=rank,
    )


def build(candidates, budget):
    counter = CharacterTokenCounter()
    package = ContextBuilderService(counter).build(
        request_id="request-1",
        query_text="Truy vấn pháp lý",
        retrieved_candidates=candidates,
        context_budget_tokens=budget,
    )
    return package, counter


def block(item, source_id):
    return format_evidence_block(item, source_id)


def test_all_candidates_fit_and_ranking_is_preserved():
    candidates = [candidate(1, 1), candidate(2, 2), candidate(3, 3)]
    package, _ = build(candidates, 10_000)
    assert [item.retrieval_final_rank for item in package.selected_evidence] == [1, 2, 3]
    assert [item.source_id for item in package.selected_evidence] == ["S1", "S2", "S3"]
    assert package.stop_reason == StopReason.NONE
    assert package.budget_exhausted is False


def test_first_candidate_too_large_returns_valid_empty_package():
    first = candidate(1, 1)
    package, _ = build([first, candidate(2, 2, "short")], len(block(first, "S1")) - 1)
    assert package.context_text == ""
    assert package.selected_evidence == []
    assert package.context_token_count == 0
    assert package.selected_count == 0
    assert package.budget_exhausted is True
    assert package.stop_reason == StopReason.TOP_EVIDENCE_EXCEEDS_CONTEXT_BUDGET


def test_first_fits_second_does_not_fit_and_no_truncation():
    first = candidate(1, 1)
    second = candidate(2, 2, "Nội dung thứ hai dài hơn.")
    budget = len(block(first, "S1")) + len(EVIDENCE_SEPARATOR + block(second, "S2")) - 1
    package, _ = build([first, second], budget)
    assert package.context_text == block(first, "S1")
    assert package.selected_evidence[0].content_text == first.content_text
    assert package.stop_reason == StopReason.TOKEN_BUDGET
    assert package.budget_exhausted is True


def test_several_fit_then_next_failure_stops_entire_loop():
    first, second, third, fourth = [candidate(i, i) for i in range(1, 5)]
    budget = (
        len(block(first, "S1"))
        + len(EVIDENCE_SEPARATOR + block(second, "S2"))
        + len(EVIDENCE_SEPARATOR + block(third, "S3"))
        - 1
    )
    package, _ = build([first, second, third, fourth], budget)
    assert [item.chunk_id for item in package.selected_evidence] == [first.chunk_id, second.chunk_id]
    assert fourth.content_text not in package.context_text
    assert package.stop_reason == StopReason.TOKEN_BUDGET


def test_candidate_after_budget_failure_is_never_token_counted():
    first = candidate(1, 1)
    second = candidate(2, 2, "X" * 100)
    third = candidate(3, 3, "FORBIDDEN_LOWER_RANK")

    class GuardCounter(CharacterTokenCounter):
        def count(self, text):
            if "FORBIDDEN_LOWER_RANK" in text:
                raise AssertionError("lower-ranked candidate was inspected")
            return super().count(text)

    budget = len(block(first, "S1"))
    package = ContextBuilderService(GuardCounter()).build(
        request_id="request-1",
        query_text="query",
        retrieved_candidates=[first, second, third],
        context_budget_tokens=budget,
    )
    assert package.selected_count == 1


def test_duplicate_before_selection_does_not_create_source_gap():
    first = candidate(1, 1, "Điều 1. Nội dung")
    duplicate = candidate(2, 2, "  Điều 1.\nNội dung  ")
    third = candidate(3, 3, "Điều 2. Nội dung")
    package, _ = build([first, duplicate, third], 10_000)
    assert package.duplicate_count == 1
    assert [item.source_id for item in package.selected_evidence] == ["S1", "S2"]
    assert [item.retrieval_final_rank for item in package.selected_evidence] == [1, 3]


def test_budget_exactly_equal_to_context_includes_candidate():
    first = candidate(1, 1)
    exact = len(block(first, "S1"))
    package, _ = build([first], exact)
    assert package.selected_count == 1
    assert package.context_token_count == exact
    assert package.budget_exhausted is False


def test_budget_one_token_smaller_rejects_whole_candidate():
    first = candidate(1, 1)
    exact = len(block(first, "S1"))
    package, _ = build([first], exact - 1)
    assert package.selected_count == 0
    assert first.content_text not in package.context_text


@pytest.mark.parametrize("count", [1, 2, 4])
def test_separator_count_and_exact_context_invariant(count):
    candidates = [candidate(i, i) for i in range(1, count + 1)]
    package, counter = build(candidates, 10_000)
    assert package.context_text.count(EVIDENCE_SEPARATOR) == count - 1
    assert not package.context_text.startswith(EVIDENCE_SEPARATOR)
    assert counter.count(package.context_text) == package.context_token_count
    expected = block(candidates[0], "S1")
    for index, item in enumerate(candidates[1:], start=2):
        expected += EVIDENCE_SEPARATOR + block(item, f"S{index}")
    assert package.context_text == expected


def test_selected_token_count_excludes_separator_context_count_includes_it():
    first, second = candidate(1, 1), candidate(2, 2)
    package, _ = build([first, second], 10_000)
    assert package.selected_evidence[0].token_count == len(block(first, "S1"))
    assert package.selected_evidence[1].token_count == len(block(second, "S2"))
    assert package.context_token_count == (
        package.selected_evidence[0].token_count
        + len(EVIDENCE_SEPARATOR)
        + package.selected_evidence[1].token_count
    )


def test_nonadditive_deterministic_counter_uses_exact_full_context_count():
    class NonAdditiveCounter:
        provider = "test"
        tokenizer_id = "fixed-width-groups-v1"

        def count(self, text):
            return (len(text) + 9) // 10

    candidates = [candidate(1, 1), candidate(2, 2)]
    package = ContextBuilderService(NonAdditiveCounter()).build(
        request_id="request-1",
        query_text="query",
        retrieved_candidates=candidates,
        context_budget_tokens=10_000,
    )
    assert package.selected_count == 2
    assert package.context_token_count == NonAdditiveCounter().count(package.context_text)
