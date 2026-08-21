import math
from collections import Counter
from statistics import mean, median


def _rate(values: list[bool]) -> float | None:
    return None if not values else sum(values) / len(values)


def _latency(values: list[float | None]) -> dict:
    cleaned = sorted(float(value) for value in values if value is not None)
    if not cleaned:
        return {"count": 0, "mean_ms": None, "p50_ms": None, "p95_ms": None}
    p95_index = max(0, math.ceil(0.95 * len(cleaned)) - 1)
    return {
        "count": len(cleaned),
        "mean_ms": mean(cleaned),
        "p50_ms": median(cleaned),
        "p95_ms": cleaned[p95_index],
    }


def aggregate_reports(case_reports: list[dict]) -> dict:
    answerable = [report for report in case_reports if report["answerable"]]
    unanswerable = [report for report in case_reports if not report["answerable"]]
    produced = [bool(report["block6"]["answer_text"].strip()) for report in answerable]
    citations_present = [bool(report["block6"]["citations"]) for report in answerable]
    structural = [report["block6"]["citation_validation"] == "PASS" for report in answerable]
    source_match = [bool(report["metrics"]["expected_source_match"]) for report in answerable]
    invalid = [bool(report["block6"]["invalid_citations"]) for report in answerable]
    missing = [report["block6"]["citation_validation"] == "MISSING_CITATIONS" for report in answerable]
    retrieved_cases = [report for report in answerable if report["metrics"]["retrieval_found"]]
    correct_abstentions = [report["block6"]["status"] == "INSUFFICIENT_EVIDENCE" for report in unanswerable]
    unsupported = [report["metrics"]["unsupported_answer"] for report in unanswerable]
    failure_counts = Counter(
        report["failure_attribution"] or "PASS" for report in case_reports
    )

    aggregate = {
        "case_count": len(case_reports),
        "answerable_count": len(answerable),
        "unanswerable_count": len(unanswerable),
        "categories": dict(sorted(Counter(report["category"] for report in case_reports).items())),
        "retrieval": {
            "hit_at_1": _rate([report["metrics"]["hit_at_1"] for report in answerable]),
            "hit_at_3": _rate([report["metrics"]["hit_at_3"] for report in answerable]),
            "hit_at_5": _rate([report["metrics"]["hit_at_5"] for report in answerable]),
            "hit_at_10": _rate([report["metrics"]["hit_at_10"] for report in answerable]),
            "mrr": mean([report["metrics"]["reciprocal_rank"] for report in answerable]) if answerable else None,
        },
        "context": {
            "expected_evidence_retention": _rate(
                [report["metrics"]["context_retained"] for report in retrieved_cases]
            ),
            "retrieved_expected_case_count": len(retrieved_cases),
            "retrieved_but_dropped_count": sum(
                report["metrics"]["retrieved_but_dropped"] for report in answerable
            ),
        },
        "generation": {
            "answer_produced_rate": _rate(produced),
            "citation_presence_rate": _rate(citations_present),
            "citation_structural_validity_rate": _rate(structural),
            "expected_source_citation_match_rate": _rate(source_match),
            "invalid_citation_rate": _rate(invalid),
            "missing_citation_rate": _rate(missing),
        },
        "unanswerable": {
            "correct_abstention_rate": _rate(correct_abstentions),
            "unsupported_answer_rate": _rate(unsupported),
            "completed_with_warning_count": sum(
                report["block6"]["status"] == "COMPLETED_WITH_WARNINGS" for report in unanswerable
            ),
        },
        "failure_counts": dict(sorted(failure_counts.items())),
        "latency": {
            stage: _latency([report["timings"].get(stage) for report in case_reports])
            for stage in ("retrieval_ms", "context_ms", "ttft_ms", "generation_ms", "total_ms")
        },
    }
    aggregate["recommended_gate_thresholds"] = {
        "status": "PROVISIONAL_RECOMMENDATIONS_ONLY_NOT_ENFORCED",
        "rationale": "Candidate review targets informed by the measured misses and legal-risk profile; they are not pass/fail criteria until explicitly approved on a broader human-reviewed dataset.",
        "retrieval_hit_at_10_min": 0.90,
        "retrieval_mrr_min": 0.85,
        "context_retention_min": 1.0,
        "citation_structural_validity_min": 0.95,
        "expected_source_match_min": 0.90,
        "unsupported_answer_rate_max": 0.10,
        "invalid_citation_rate_max": 0.0,
        "missing_citation_rate_max": 0.05,
    }
    return aggregate
