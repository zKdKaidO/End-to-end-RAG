import pytest

from evaluation.context_metrics import context_retention, evidence_solution_present
from evaluation.gate import aggregate_reports
from evaluation.generation_metrics import classify_failure, expected_source_match, unsupported_answer
from evaluation.retrieval_metrics import acceptable_solution_rank, hit_at_k, reciprocal_rank
from evaluation.schemas import FailureAttribution


SOLUTIONS = [["a"], ["b", "c"]]


def test_hit_at_k_and_acceptable_multi_evidence_semantics():
    ranked = ["x", "b", "y", "c", "a"]
    assert acceptable_solution_rank(ranked, SOLUTIONS) == 4
    assert hit_at_k(ranked, SOLUTIONS, 1) == 0
    assert hit_at_k(ranked, SOLUTIONS, 3) == 0
    assert hit_at_k(ranked, SOLUTIONS, 4) == 1
    assert reciprocal_rank(ranked, SOLUTIONS) == pytest.approx(0.25)
    assert acceptable_solution_rank(["x", "a", "b", "c"], SOLUTIONS) == 2


def test_context_retention_distinguishes_miss_from_drop():
    assert context_retention(["x", "a"], ["x"], SOLUTIONS) == (True, False, True)
    assert context_retention(["x"], ["x"], SOLUTIONS) == (False, False, False)
    assert context_retention(["b", "c"], ["b", "c"], SOLUTIONS) == (True, True, False)


def test_expected_source_match_requires_complete_acceptable_solution():
    assert expected_source_match(["a"], SOLUTIONS) is True
    assert expected_source_match(["b"], SOLUTIONS) is False
    assert expected_source_match(["c", "b"], SOLUTIONS) is True


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({"answerable": True, "retrieval_found": False, "context_retained": False, "status": "COMPLETED", "answer_text": "a", "citation_validation": "PASS", "expected_citation_match": False}, FailureAttribution.RETRIEVAL_MISS),
        ({"answerable": True, "retrieval_found": True, "context_retained": False, "status": "COMPLETED", "answer_text": "a", "citation_validation": "PASS", "expected_citation_match": False}, FailureAttribution.CONTEXT_DROP),
        ({"answerable": True, "retrieval_found": True, "context_retained": True, "status": "COMPLETED_WITH_WARNINGS", "answer_text": "a", "citation_validation": "MISSING_CITATIONS", "expected_citation_match": False}, FailureAttribution.GENERATION_MISSING_CITATION),
        ({"answerable": True, "retrieval_found": True, "context_retained": True, "status": "COMPLETED_WITH_WARNINGS", "answer_text": "a", "citation_validation": "INVALID_REFERENCES", "expected_citation_match": False}, FailureAttribution.GENERATION_INVALID_CITATION),
        ({"answerable": True, "retrieval_found": True, "context_retained": True, "status": "COMPLETED", "answer_text": "a", "citation_validation": "PASS", "expected_citation_match": False}, FailureAttribution.GENERATION_WRONG_SOURCE),
        ({"answerable": False, "retrieval_found": False, "context_retained": False, "status": "COMPLETED", "answer_text": "unsupported", "citation_validation": "PASS", "expected_citation_match": None}, FailureAttribution.UNSUPPORTED_ANSWER),
        ({"answerable": True, "retrieval_found": True, "context_retained": True, "status": "INSUFFICIENT_EVIDENCE", "answer_text": "insufficient", "citation_validation": "PASS", "expected_citation_match": False}, FailureAttribution.INSUFFICIENT_EVIDENCE_FALSE_NEGATIVE),
    ],
)
def test_failure_attribution(kwargs, expected):
    assert classify_failure(**kwargs) == expected


def test_unanswerable_classification():
    assert unsupported_answer(False, "COMPLETED", "answer") is True
    assert unsupported_answer(False, "INSUFFICIENT_EVIDENCE", "insufficient") is False
    assert classify_failure(
        answerable=False, retrieval_found=False, context_retained=False,
        status="INSUFFICIENT_EVIDENCE", answer_text="insufficient",
        citation_validation="PASS", expected_citation_match=None,
    ) is None


def _report(answerable, *, hit=True, status="COMPLETED", validation="PASS", source=True, failure=None):
    return {
        "answerable": answerable,
        "category": "DIRECT_FACT" if answerable else "UNANSWERABLE",
        "block6": {
            "answer_text": "answer", "citations": ([{"source_id": "S1"}] if validation == "PASS" else []),
            "invalid_citations": (["S99"] if validation == "INVALID_REFERENCES" else []),
            "citation_validation": validation, "status": status,
        },
        "metrics": {
            "hit_at_1": hit, "hit_at_3": hit, "hit_at_5": hit, "hit_at_10": hit,
            "reciprocal_rank": (1.0 if hit else 0.0), "retrieval_found": hit,
            "context_retained": hit, "retrieved_but_dropped": False,
            "expected_source_match": source if answerable else None,
            "unsupported_answer": (not answerable and status != "INSUFFICIENT_EVIDENCE"),
        },
        "failure_attribution": failure,
        "timings": {"retrieval_ms": 10, "context_ms": 2, "ttft_ms": 5, "generation_ms": 20, "total_ms": 32},
    }


def test_aggregate_calculations_have_explicit_denominators():
    aggregate = aggregate_reports([
        _report(True),
        _report(True, hit=False, validation="MISSING_CITATIONS", source=False, failure="RETRIEVAL_MISS"),
        _report(False, status="INSUFFICIENT_EVIDENCE"),
        _report(False, status="COMPLETED", failure="UNSUPPORTED_ANSWER"),
    ])
    assert aggregate["retrieval"]["hit_at_10"] == 0.5
    assert aggregate["retrieval"]["mrr"] == 0.5
    assert aggregate["context"]["expected_evidence_retention"] == 1.0
    assert aggregate["generation"]["citation_presence_rate"] == 0.5
    assert aggregate["generation"]["expected_source_citation_match_rate"] == 0.5
    assert aggregate["unanswerable"]["correct_abstention_rate"] == 0.5
    assert aggregate["unanswerable"]["unsupported_answer_rate"] == 0.5
    assert aggregate["recommended_gate_thresholds"]["status"] == "PROVISIONAL_RECOMMENDATIONS_ONLY_NOT_ENFORCED"
