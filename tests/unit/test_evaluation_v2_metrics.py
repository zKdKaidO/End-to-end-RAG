import pytest

from evaluation.v2_metrics import (
    classify_v2_failure,
    document_hit_at_k,
    evidence_set_metrics,
    latency_summary,
)


def test_evidence_set_metrics_requires_complete_multi_evidence_solution():
    solutions = [["a", "b", "c"]]
    partial = evidence_set_metrics(["x", "a", "c"], solutions)
    assert partial == {
        "complete": False,
        "partial": True,
        "recall": pytest.approx(2 / 3),
        "complete_rank": None,
    }
    complete = evidence_set_metrics(["c", "x", "a", "b"], solutions)
    assert complete["complete"] is True
    assert complete["partial"] is False
    assert complete["recall"] == 1.0
    assert complete["complete_rank"] == 4


def test_evidence_set_metrics_selects_best_valid_alternative():
    result = evidence_set_metrics(["b", "c"], [["a"], ["b", "c"]])
    assert result["complete"] is True
    assert result["recall"] == 1.0
    assert result["complete_rank"] == 2


def test_document_hit_requires_every_expected_document_within_cutoff():
    ranked = ["doc-a", "doc-a", "doc-b"]
    assert document_hit_at_k(ranked, ["doc-a", "doc-b"], 2) is False
    assert document_hit_at_k(ranked, ["doc-a", "doc-b"], 3) is True
    with pytest.raises(ValueError):
        document_hit_at_k(ranked, ["doc-a"], 0)


def _case(*, answerable=True, retrieval_complete=True, retrieval_partial=False, status="COMPLETED",
          validation="PASS", citation_complete=True, context_complete=True, expected_docs=None,
          final_docs=None):
    return {
        "answerable": answerable,
        "expected_document_ids": expected_docs or ["doc-a"],
        "block4": {"final_candidates": [{"document_id": value} for value in (final_docs or ["doc-a"])]},
        "block6": {"status": status, "citation_validation": validation},
        "metrics_v2": {
            "retrieval_evidence": {"complete": retrieval_complete, "partial": retrieval_partial},
            "context_evidence": {"complete": context_complete},
            "citation_evidence": {"complete": citation_complete},
        },
    }


@pytest.mark.parametrize(
    "case,label",
    [
        (_case(), "PASS"),
        (_case(retrieval_complete=False, final_docs=["doc-b"]), "WRONG_DOCUMENT"),
        (_case(retrieval_complete=False, retrieval_partial=True), "PARTIAL_MULTI_EVIDENCE_RETRIEVAL"),
        (_case(retrieval_complete=False), "RETRIEVAL_MISS"),
        (_case(context_complete=False), "CONTEXT_DROP"),
        (_case(status="INSUFFICIENT_EVIDENCE"), "FALSE_ABSTENTION"),
        (_case(validation="MISSING_CITATIONS", citation_complete=False), "GENERATION_MISSING_CITATION"),
        (_case(validation="INVALID_REFERENCES", citation_complete=False), "GENERATION_INVALID_CITATION"),
        (_case(citation_complete=False), "GENERATION_WRONG_SOURCE"),
        (_case(answerable=False, status="INSUFFICIENT_EVIDENCE"), "PASS"),
        (_case(answerable=False, status="COMPLETED"), "UNSUPPORTED_ANSWER"),
    ],
)
def test_v2_failure_attribution_is_deterministic(case, label):
    assert classify_v2_failure(case) == label


def test_latency_summary_uses_nearest_rank_p95():
    result = latency_summary([1, 2, 3, 4, None])
    assert result == {"count": 4, "mean_ms": 2.5, "p50_ms": 2.5, "p95_ms": 4.0}
