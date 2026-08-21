"""Deterministic, ground-truth-based metrics for Legal Evaluation V2."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from statistics import mean, median
from typing import Any, Sequence

from evaluation.retrieval_metrics import acceptable_solution_rank


FAILURE_LABELS = (
    "PASS",
    "RETRIEVAL_MISS",
    "WRONG_DOCUMENT",
    "PARTIAL_MULTI_EVIDENCE_RETRIEVAL",
    "CONTEXT_DROP",
    "GENERATION_MISSING_CITATION",
    "GENERATION_INVALID_CITATION",
    "GENERATION_WRONG_SOURCE",
    "FALSE_ABSTENTION",
    "UNSUPPORTED_ANSWER",
    "AMBIGUOUS",
    "OTHER",
)


def rate(values: Sequence[bool]) -> float | None:
    return None if not values else sum(values) / len(values)


def latency_summary(values: Sequence[float | None]) -> dict[str, float | int | None]:
    cleaned = sorted(float(value) for value in values if value is not None)
    if not cleaned:
        return {"count": 0, "mean_ms": None, "p50_ms": None, "p95_ms": None}
    return {
        "count": len(cleaned),
        "mean_ms": mean(cleaned),
        "p50_ms": median(cleaned),
        "p95_ms": cleaned[max(0, math.ceil(0.95 * len(cleaned)) - 1)],
    }


def evidence_set_metrics(
    observed_chunk_ids: Sequence[str], acceptable_evidence_sets: Sequence[Sequence[str]]
) -> dict[str, Any]:
    """Score the best acceptable evidence solution; complete requires every required chunk."""
    observed = set(observed_chunk_ids)
    recalls = [len(observed.intersection(solution)) / len(solution) for solution in acceptable_evidence_sets]
    best_recall = max(recalls, default=0.0)
    complete = any(set(solution).issubset(observed) for solution in acceptable_evidence_sets)
    return {
        "complete": complete,
        "partial": 0.0 < best_recall < 1.0,
        "recall": best_recall,
        "complete_rank": acceptable_solution_rank(observed_chunk_ids, acceptable_evidence_sets),
    }


def document_hit_at_k(
    ranked_document_ids: Sequence[str], expected_document_ids: Sequence[str], k: int
) -> bool:
    if k <= 0:
        raise ValueError("k must be positive")
    return bool(expected_document_ids) and set(expected_document_ids).issubset(ranked_document_ids[:k])


def classify_v2_failure(case: dict[str, Any]) -> str:
    if not case["answerable"]:
        return "PASS" if case["block6"]["status"] == "INSUFFICIENT_EVIDENCE" else "UNSUPPORTED_ANSWER"

    metrics = case["metrics_v2"]
    retrieval = metrics["retrieval_evidence"]
    if not retrieval["complete"]:
        if retrieval["partial"]:
            return "PARTIAL_MULTI_EVIDENCE_RETRIEVAL"
        final_docs = {item["document_id"] for item in case["block4"]["final_candidates"]}
        if not final_docs.intersection(case["expected_document_ids"]):
            return "WRONG_DOCUMENT"
        return "RETRIEVAL_MISS"
    if not metrics["context_evidence"]["complete"]:
        return "CONTEXT_DROP"
    if case["block6"]["status"] == "INSUFFICIENT_EVIDENCE":
        return "FALSE_ABSTENTION"
    if case["block6"]["citation_validation"] == "INVALID_REFERENCES":
        return "GENERATION_INVALID_CITATION"
    if case["block6"]["citation_validation"] == "MISSING_CITATIONS":
        return "GENERATION_MISSING_CITATION"
    if not metrics["citation_evidence"]["complete"]:
        return "GENERATION_WRONG_SOURCE"
    return "PASS"


def enrich_case(case: dict[str, Any], lexical_mode: str) -> dict[str, Any]:
    final = case["block4"]["final_candidates"]
    final_ids = [item["chunk_id"] for item in final]
    final_docs = [item["document_id"] for item in final]
    dense_ids = [item["chunk_id"] for item in case["block4"]["dense_candidates"]]
    lexical_ids = [item["chunk_id"] for item in case["block4"]["lexical_candidates"]]
    selected_ids = case["block5"]["selected_chunk_ids"]
    cited_ids = case["block6"]["mapped_chunk_ids"]
    solutions = case["acceptable_evidence_sets"]

    if case["answerable"]:
        retrieval = evidence_set_metrics(final_ids, solutions)
        dense = evidence_set_metrics(dense_ids, solutions)
        lexical = evidence_set_metrics(lexical_ids, solutions)
        context = evidence_set_metrics(selected_ids, solutions)
        citation = evidence_set_metrics(cited_ids, solutions)
        document_hits = {
            f"hit_at_{k}": document_hit_at_k(final_docs, case["expected_document_ids"], k)
            for k in (1, 3, 5, 10)
        }
        multi = min((len(solution) for solution in solutions), default=0) > 1
        multi_document = len(set(case["expected_document_ids"])) > 1
        dense_rank = dense["complete_rank"]
        final_rank = retrieval["complete_rank"]
        lexical_improved = final_rank is not None and (dense_rank is None or final_rank < dense_rank)
        lexical_harmed = dense_rank is not None and dense_rank <= 10 and (
            final_rank is None or final_rank > dense_rank
        )
    else:
        retrieval = dense = lexical = context = citation = None
        document_hits = {f"hit_at_{k}": None for k in (1, 3, 5, 10)}
        multi = multi_document = lexical_improved = lexical_harmed = False

    budget = case["block5"]["context_budget_tokens"]
    case["metrics_v2"] = {
        "retrieval_evidence": retrieval,
        "dense_evidence": dense,
        "lexical_evidence": lexical,
        "context_evidence": context,
        "citation_evidence": citation,
        "document_retrieval": document_hits,
        "is_multi_evidence": multi,
        "is_multi_document": multi_document,
        "lexical_mode": lexical_mode,
        "dense_lexical_overlap_count": len(set(dense_ids).intersection(lexical_ids)),
        "lexical_improved_expected_rank": lexical_improved,
        "lexical_harmed_expected_rank": lexical_harmed,
        "context_utilization": case["block5"]["context_token_count"] / budget if budget else None,
    }
    case["failure_attribution_v2"] = classify_v2_failure(case)
    return case


def _category_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    answerable = [item for item in items if item["answerable"]]
    unanswerable = [item for item in items if not item["answerable"]]
    return {
        "case_count": len(items),
        "answerable_count": len(answerable),
        "unanswerable_count": len(unanswerable),
        "hit_at_10": rate([item["metrics"]["hit_at_10"] for item in answerable]),
        "document_hit_at_10": rate(
            [item["metrics_v2"]["document_retrieval"]["hit_at_10"] for item in answerable]
        ),
        "expected_source_citation_match": rate(
            [item["metrics_v2"]["citation_evidence"]["complete"] for item in answerable]
        ),
        "correct_abstention": rate(
            [item["block6"]["status"] == "INSUFFICIENT_EVIDENCE" for item in unanswerable]
        ),
        "failure_counts": dict(sorted(Counter(item["failure_attribution_v2"] for item in items).items())),
    }


def aggregate_v2(cases: list[dict[str, Any]], scale: dict[str, Any]) -> dict[str, Any]:
    answerable = [item for item in cases if item["answerable"]]
    unanswerable = [item for item in cases if not item["answerable"]]
    retrieved = [item for item in answerable if item["metrics_v2"]["retrieval_evidence"]["complete"]]
    multi = [item for item in answerable if item["metrics_v2"]["is_multi_evidence"]]
    multi_document = [item for item in answerable if item["metrics_v2"]["is_multi_document"]]
    category_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in cases:
        category_groups[item["category"]].append(item)
    failure_counts = Counter(item["failure_attribution_v2"] for item in cases)
    lexical_modes = Counter(item["metrics_v2"]["lexical_mode"] for item in cases)
    statuses = Counter(item["block6"]["status"] for item in cases)

    produced = [
        item["block6"]["status"] != "INSUFFICIENT_EVIDENCE" and bool(item["block6"]["answer_text"].strip())
        for item in answerable
    ]
    aggregate = {
        "case_count": len(cases),
        "answerable_count": len(answerable),
        "unanswerable_count": len(unanswerable),
        "retrieval": {
            f"hit_at_{k}": rate([item["metrics"][f"hit_at_{k}"] for item in answerable])
            for k in (1, 3, 5, 10)
        },
        "document_retrieval": {
            f"hit_at_{k}": rate(
                [item["metrics_v2"]["document_retrieval"][f"hit_at_{k}"] for item in answerable]
            )
            for k in (1, 3, 5, 10)
        },
        "multi_evidence": {
            "case_count": len(multi),
            "complete_retrieval_rate": rate(
                [item["metrics_v2"]["retrieval_evidence"]["complete"] for item in multi]
            ),
            "partial_retrieval_rate": rate(
                [item["metrics_v2"]["retrieval_evidence"]["partial"] for item in multi]
            ),
            "average_required_evidence_recall": (
                mean(item["metrics_v2"]["retrieval_evidence"]["recall"] for item in multi)
                if multi else None
            ),
        },
        "lexical": {
            "non_empty_rate": rate([bool(item["block4"]["lexical_candidates"]) for item in cases]),
            "mode_counts": {mode: lexical_modes.get(mode, 0) for mode in ("STRICT_MATCH", "SELECTIVE_FALLBACK", "NO_MATCH")},
            "expected_evidence_hit_rate": rate(
                [item["metrics_v2"]["lexical_evidence"]["complete"] for item in answerable]
            ),
            "mean_dense_lexical_overlap": mean(
                item["metrics_v2"]["dense_lexical_overlap_count"] for item in cases
            ) if cases else None,
            "improved_case_count": sum(item["metrics_v2"]["lexical_improved_expected_rank"] for item in answerable),
            "harmed_case_count": sum(item["metrics_v2"]["lexical_harmed_expected_rank"] for item in answerable),
            "improved_case_ids": [
                item["case_id"] for item in answerable
                if item["metrics_v2"]["lexical_improved_expected_rank"]
            ],
            "harmed_case_ids": [
                item["case_id"] for item in answerable
                if item["metrics_v2"]["lexical_harmed_expected_rank"]
            ],
        },
        "context": {
            "expected_evidence_retention": rate(
                [item["metrics_v2"]["context_evidence"]["complete"] for item in retrieved]
            ),
            "retrieved_expected_case_count": len(retrieved),
            "retrieved_but_dropped_count": sum(
                item["metrics_v2"]["retrieval_evidence"]["complete"]
                and not item["metrics_v2"]["context_evidence"]["complete"]
                for item in answerable
            ),
            "budget_exhausted_count": sum(item["block5"]["budget_exhausted"] for item in cases),
            "top_evidence_exceeds_budget_count": sum(
                item["block5"]["stop_reason"] == "TOP_EVIDENCE_EXCEEDS_CONTEXT_BUDGET"
                for item in cases
            ),
            "multi_evidence_complete_rate": rate(
                [item["metrics_v2"]["context_evidence"]["complete"] for item in multi]
            ),
            "average_utilization": mean(
                item["metrics_v2"]["context_utilization"] for item in cases
            ) if cases else None,
        },
        "generation": {
            "answer_produced_rate": rate(produced),
            "citation_presence_rate": rate([bool(item["block6"]["citations"]) for item in answerable]),
            "citation_structural_validity_rate": rate([
                bool(item["block6"]["citations"]) and item["block6"]["citation_validation"] == "PASS"
                for item in answerable
            ]),
            "expected_source_citation_match_rate": rate(
                [item["metrics_v2"]["citation_evidence"]["complete"] for item in answerable]
            ),
            "missing_citation_rate": rate([
                item["block6"]["citation_validation"] == "MISSING_CITATIONS" for item in answerable
            ]),
            "invalid_citation_rate": rate([bool(item["block6"]["invalid_citations"]) for item in answerable]),
            "multi_document_citation_completeness": rate([
                set(item["expected_document_ids"]).issubset(item["block6"]["mapped_document_ids"])
                for item in multi_document
            ]),
            "status_counts": dict(sorted(statuses.items())),
        },
        "answerability": {
            "correct_abstention_rate": rate([
                item["block6"]["status"] == "INSUFFICIENT_EVIDENCE" for item in unanswerable
            ]),
            "false_abstention_rate": rate([
                item["block6"]["status"] == "INSUFFICIENT_EVIDENCE" for item in answerable
            ]),
            "unsupported_direct_answer_rate": rate([
                item["block6"]["status"] != "INSUFFICIENT_EVIDENCE" for item in unanswerable
            ]),
            "answerable_accepted_rate": rate([
                item["block6"]["status"] != "INSUFFICIENT_EVIDENCE" for item in answerable
            ]),
            "hard_unanswerable": _category_summary(
                [item for item in cases if item["category"] == "HARD_UNANSWERABLE"]
            ),
            "out_of_corpus": _category_summary(
                [item for item in cases if item["category"] == "OUT_OF_CORPUS"]
            ),
        },
        "failure_counts": {label: failure_counts.get(label, 0) for label in FAILURE_LABELS},
        "category_breakdown": {
            category: _category_summary(items) for category, items in sorted(category_groups.items())
        },
        "latency": {
            stage: latency_summary([item["timings"].get(stage) for item in cases])
            for stage in ("retrieval_ms", "context_ms", "ttft_ms", "generation_ms", "total_ms")
        },
        "scale": scale,
    }
    aggregate["retrieval"]["mrr"] = (
        mean(item["metrics"]["reciprocal_rank"] for item in answerable) if answerable else None
    )
    aggregate["retrieval"]["expected_evidence_rank_distribution"] = {
        "rank_1": sum(item["metrics"]["expected_evidence_rank"] == 1 for item in answerable),
        "rank_2_3": sum(
            item["metrics"]["expected_evidence_rank"] is not None
            and 2 <= item["metrics"]["expected_evidence_rank"] <= 3
            for item in answerable
        ),
        "rank_4_5": sum(
            item["metrics"]["expected_evidence_rank"] is not None
            and 4 <= item["metrics"]["expected_evidence_rank"] <= 5
            for item in answerable
        ),
        "rank_6_10": sum(
            item["metrics"]["expected_evidence_rank"] is not None
            and 6 <= item["metrics"]["expected_evidence_rank"] <= 10
            for item in answerable
        ),
        "not_complete_in_top_10": sum(
            item["metrics"]["expected_evidence_rank"] is None for item in answerable
        ),
    }
    # Compatibility alias for the existing Evaluation V1 cockpit cards.
    aggregate["unanswerable"] = {
        "correct_abstention_rate": aggregate["answerability"]["correct_abstention_rate"],
        "unsupported_answer_rate": aggregate["answerability"]["unsupported_direct_answer_rate"],
    }
    return aggregate
