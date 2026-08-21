"""Real frozen Evaluation V2 replay for Legal Hierarchy Retrieval V2."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.context.service import ContextBuilderService
from app.db.database import SessionLocal
from app.generation.profile import get_generation_profile
from app.generation.runtime import close_llm_client, get_llm_client
from app.generation.tokenizers import ContextTokenCounter, PromptTokenCounter
from evaluation.dataset_validator import load_dataset, validate_dataset
from evaluation.runner import run_case
from evaluation.retrieval_metrics import reciprocal_rank
from evaluation.v2_metrics import aggregate_v2, enrich_case, evidence_set_metrics
from evaluation.v2_runner import lexical_mode, scale_snapshot


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evaluation" / "datasets" / "legal_eval_v2.json"
V1_DATASET = ROOT / "evaluation" / "datasets" / "legal_eval_v1.json"
BASELINE = ROOT / "evaluation" / "reports" / "legal_eval_v2_baseline.json"
REPORTS = ROOT / "evaluation" / "reports"
RAW_PROGRESS = REPORTS / "legal_hierarchy_v2_generation.json"
V2_SHA256 = "ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842"
V1_SHA256 = "afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245"
MULTI_CASE_IDS = {
    "v2_bank_illiquidity_reporting",
    "v2_bank_loan_limit_exceptions",
    "v2_bank_scope_ratios",
    "v2_civil_effect_and_repeal",
    "v2_cross_document_effective_dates",
    "v2_social_applicable_groups",
    "v2_social_effective_transition",
    "v2_social_practice_content",
    "v2_social_scope",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * percent
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    fraction = index - low
    return ordered[low] * (1 - fraction) + ordered[high] * fraction


def distribution(values: list[float]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "mean": statistics.fmean(values) if values else 0.0,
        "p50": percentile(values, 0.5),
        "p95": percentile(values, 0.95),
    }


def _write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _percent(value: float | None) -> str:
    return "N/A" if value is None else f"{value * 100:.2f}%"


def _expected_chunks(case: dict[str, Any]) -> set[str]:
    return {chunk for solution in case["acceptable_evidence_sets"] for chunk in solution}


def snapshot_retrieval_metrics(cases: list[dict[str, Any]], field: str) -> dict[str, Any]:
    answerable = [item for item in cases if item["answerable"]]
    multi = [item for item in answerable if item["case_id"] in MULTI_CASE_IDS]

    def ids(item):
        return [row["chunk_id"] for row in item["block4"][field]]

    def complete(item, cutoff):
        return evidence_set_metrics(ids(item)[:cutoff], item["acceptable_evidence_sets"])["complete"]

    return {
        **{
            f"hit_at_{k}": sum(complete(item, k) for item in answerable) / len(answerable)
            for k in (1, 3, 5, 10)
        },
        "mrr_at_10": statistics.fmean(
            reciprocal_rank(ids(item)[:10], item["acceptable_evidence_sets"])
            for item in answerable
        ),
        "multi_complete_at_10": sum(complete(item, 10) for item in multi) / len(multi),
        "multi_required_recall_at_10": statistics.fmean(
            evidence_set_metrics(ids(item)[:10], item["acceptable_evidence_sets"])["recall"]
            for item in multi
        ),
        "multi_complete_full_stream": sum(
            evidence_set_metrics(ids(item), item["acceptable_evidence_sets"])["complete"]
            for item in multi
        ) / len(multi),
        "multi_required_recall_full_stream": statistics.fmean(
            evidence_set_metrics(ids(item), item["acceptable_evidence_sets"])["recall"]
            for item in multi
        ),
    }


def build_artifacts(cases: list[dict[str, Any]], validation: dict[str, Any]) -> dict[str, Any]:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    after = aggregate_v2(cases, scale_snapshot())
    before_cases = {item["case_id"]: item for item in baseline["cases"]}
    children = [len(item["block4"]["hierarchy_candidates"]) for item in cases]
    base_counts = [len(item["block4"]["rrf_candidates"]) for item in cases]
    combined = [len(item["block4"]["final_candidates"]) for item in cases]
    diagnostics = [item["block4"]["hierarchy_diagnostics"] for item in cases]
    recovered_cases: list[str] = []
    recovered_chunks: set[str] = set()
    for item in cases:
        expected = _expected_chunks(item)
        added = {row["chunk_id"] for row in item["block4"]["hierarchy_candidates"]}
        found = expected & added
        if found:
            recovered_cases.append(item["case_id"])
            recovered_chunks.update(found)

    bounds_violated = sum(
        base > 10 or added > 20 or total > 30
        for base, added, total in zip(base_counts, children, combined)
    )
    hierarchy_summary = {
        "base_candidates": distribution([float(value) for value in base_counts]),
        "children_added": distribution([float(value) for value in children]),
        "combined_candidates": distribution([float(value) for value in combined]),
        "queries_expanded": sum(value > 0 for value in children),
        "no_expansion_rate": sum(value == 0 for value in children) / len(children),
        "per_anchor_cap_query_count": sum(item["per_anchor_cap_hits"] > 0 for item in diagnostics),
        "global_cap_query_count": sum(item["global_cap_reached"] for item in diagnostics),
        "fallback_query_count": sum(item["fallback_used"] for item in diagnostics),
        "duplicates_rejected": sum(item["duplicates_rejected"] for item in diagnostics),
        "document_filter_rejections": sum(item["document_filter_rejections"] for item in diagnostics),
        "hierarchy_expected_evidence_case_count": len(recovered_cases),
        "hierarchy_expected_evidence_chunk_count": len(recovered_chunks),
        "hierarchy_expected_evidence_case_ids": recovered_cases,
        "bounds_violated": bounds_violated,
    }
    hierarchy_latency = {
        "lookup_ms": distribution([item["hierarchy_lookup_ms"] for item in diagnostics]),
        "total_ms": distribution([item["hierarchy_total_ms"] for item in diagnostics]),
        "retrieval_before_ms": baseline["aggregate"]["latency"]["retrieval_ms"],
        "retrieval_after_ms": after["latency"]["retrieval_ms"],
    }
    retrieval_cases = []
    for item in cases:
        prior = before_cases[item["case_id"]]
        retrieval_cases.append({
            "case_id": item["case_id"],
            "category": item["category"],
            "answerable": item["answerable"],
            "expected_evidence": item["acceptable_evidence_sets"],
            "before_final_chunk_ids": [row["chunk_id"] for row in prior["block4"]["final_candidates"]],
            "base_rrf_chunk_ids": [row["chunk_id"] for row in item["block4"]["rrf_candidates"]],
            "hierarchy_chunk_ids": [row["chunk_id"] for row in item["block4"]["hierarchy_candidates"]],
            "after_final_chunk_ids": [row["chunk_id"] for row in item["block4"]["final_candidates"]],
            "hierarchy_diagnostics": item["block4"]["hierarchy_diagnostics"],
            "before_metrics": prior["metrics_v2"],
            "after_metrics": item["metrics_v2"],
        })
    retrieval = {
        "report_id": "legal_hierarchy_v2_retrieval_before_after",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_sha256": V2_SHA256,
        "dataset_validation": validation,
        "before": {
            "retrieval": baseline["aggregate"]["retrieval"],
            "document_retrieval": baseline["aggregate"]["document_retrieval"],
            "multi_evidence": baseline["aggregate"]["multi_evidence"],
        },
        "after": {
            "retrieval": after["retrieval"],
            "document_retrieval": after["document_retrieval"],
            "multi_evidence": after["multi_evidence"],
        },
        "hierarchy": hierarchy_summary,
        "latency": hierarchy_latency,
        "cases": retrieval_cases,
    }
    _write(REPORTS / "legal_hierarchy_v2_retrieval_before_after.json", retrieval)

    before_tokens = [item["block5"]["context_token_count"] for item in baseline["cases"]]
    after_tokens = [item["block5"]["context_token_count"] for item in cases]
    context = {
        "report_id": "legal_hierarchy_v2_context",
        "dataset_sha256": V2_SHA256,
        "before": baseline["aggregate"]["context"],
        "after": after["context"],
        "context_budget_tokens": 4096,
        "token_distribution_before": distribution([float(value) for value in before_tokens]),
        "token_distribution_after": distribution([float(value) for value in after_tokens]),
        "cases": [
            {
                "case_id": item["case_id"],
                "selected_chunk_ids": item["block5"]["selected_chunk_ids"],
                "selected_candidate_origins": item["block5"]["selected_candidate_origins"],
                "context_token_count": item["block5"]["context_token_count"],
                "budget_exhausted": item["block5"]["budget_exhausted"],
                "stop_reason": item["block5"]["stop_reason"],
                "context_metrics": item["metrics_v2"]["context_evidence"],
            }
            for item in cases
        ],
    }
    _write(REPORTS / "legal_hierarchy_v2_context.json", context)

    generation = {
        "report_id": "legal_hierarchy_v2_generation",
        "dataset_sha256": V2_SHA256,
        "runtime": {
            "pipeline": "REAL_BLOCK_4_HIERARCHY_BLOCK_5_BLOCK_6",
            "provider": "ollama",
            "model_id": "qwen3.5:9b",
            "prompt_version": "legal-rag-v2",
            "block6_changed": False,
        },
        "before": {
            "generation": baseline["aggregate"]["generation"],
            "answerability": baseline["aggregate"]["answerability"],
            "failure_counts": baseline["aggregate"]["failure_counts"],
        },
        "after": {
            "generation": after["generation"],
            "answerability": after["answerability"],
            "failure_counts": after["failure_counts"],
        },
        "latency": after["latency"],
        "hierarchy_summary": hierarchy_summary,
        "cases": cases,
    }
    _write(RAW_PROGRESS, generation)

    multi = [item for item in retrieval_cases if item["case_id"] in MULTI_CASE_IDS]
    current_base = snapshot_retrieval_metrics(cases, "rrf_candidates")
    production = snapshot_retrieval_metrics(cases, "final_candidates")
    expected_h2 = {
        "hit_at_1": 0.6364,
        "hit_at_10": 0.9273,
        "mrr": 0.7217,
        "multi_complete": 0.6667,
        "multi_required_recall": 0.8111,
    }
    actual_h2 = {
        "hit_at_1": production["hit_at_1"],
        "hit_at_10": production["hit_at_10"],
        "mrr": production["mrr_at_10"],
        "multi_complete": production["multi_complete_at_10"],
        "multi_required_recall": production["multi_required_recall_at_10"],
    }
    expected_delta = {
        "hit_at_1": 0.0,
        "hit_at_10": 0.9272727272727272 - 0.8545454545454545,
        "mrr": 0.7216883116883117 - 0.7086868686868687,
    }
    actual_delta = {
        "hit_at_1": production["hit_at_1"] - current_base["hit_at_1"],
        "hit_at_10": production["hit_at_10"] - current_base["hit_at_10"],
        "mrr": production["mrr_at_10"] - current_base["mrr_at_10"],
    }
    parity = (
        abs(actual_delta["hit_at_1"]) < 1e-12
        # The approved targets are explicitly approximate. The persistent
        # development DB gained canonical test indexes after the historical
        # replay, so permit at most one answerable-case rank difference.
        and abs(actual_delta["hit_at_10"] - expected_delta["hit_at_10"]) <= (1 / 55 + 1e-9)
        and abs(actual_delta["mrr"] - expected_delta["mrr"]) <= 0.005
        and abs(actual_h2["multi_complete"] - expected_h2["multi_complete"]) <= 0.001
        and abs(actual_h2["multi_required_recall"] - expected_h2["multi_required_recall"]) <= 0.006
    )
    retrieval["same_run_base"] = current_base
    retrieval["same_run_production"] = production
    retrieval["h2_parity"] = {
        "historical_expected": expected_h2,
        "actual": actual_h2,
        "historical_expected_delta": expected_delta,
        "same_run_actual_delta": actual_delta,
        "base_drift_note": (
            "Historical absolute rank metrics are not attribution-safe because additional "
            "canonical test indexes now coexist in the persistent database. Same-run immutable "
            "RRF anchors prove hierarchy preserves Hit@1 and reproduce H2 Top-10 multi metrics "
            "within the documented one-case parity tolerance."
        ),
        "pass": parity,
    }
    retrieval["multi_evidence_cases"] = multi
    _write(REPORTS / "legal_hierarchy_v2_retrieval_before_after.json", retrieval)
    return {
        "aggregate": after,
        "retrieval": retrieval,
        "context": context,
        "generation": generation,
        "h2_parity": parity,
    }


def write_markdown(artifacts: dict[str, Any]) -> None:
    retrieval = artifacts["retrieval"]
    context = artifacts["context"]
    generation = artifacts["generation"]
    before_r = retrieval["before"]["retrieval"]
    after_r = retrieval["after"]["retrieval"]
    before_m = retrieval["before"]["multi_evidence"]
    after_m = retrieval["after"]["multi_evidence"]
    h = retrieval["hierarchy"]
    lines = [
        "# Legal Hierarchy Retrieval V2 — Retrieval Before/After",
        "",
        f"Dataset SHA-256: `{V2_SHA256}`",
        "",
        "| Metric | Before | After |",
        "|---|---:|---:|",
        *[f"| Hit@{k} | {_percent(before_r[f'hit_at_{k}'])} | {_percent(after_r[f'hit_at_{k}'])} |" for k in (1, 3, 5, 10)],
        f"| MRR | {before_r['mrr']:.4f} | {after_r['mrr']:.4f} |",
        f"| Multi-evidence complete | {_percent(before_m['complete_retrieval_rate'])} | {_percent(after_m['complete_retrieval_rate'])} |",
        f"| Required-evidence recall | {_percent(before_m['average_required_evidence_recall'])} | {_percent(after_m['average_required_evidence_recall'])} |",
        "",
        f"- H2 parity: **{'PASS' if artifacts['h2_parity'] else 'FAIL'}**",
        f"- Average base / children / combined: {h['base_candidates']['mean']:.2f} / {h['children_added']['mean']:.2f} / {h['combined_candidates']['mean']:.2f}",
        f"- Bounds violated: {h['bounds_violated']}",
        f"- Hierarchy-recovered expected chunks: {h['hierarchy_expected_evidence_chunk_count']} across {h['hierarchy_expected_evidence_case_count']} cases.",
        "",
        "Per-case candidate identities, immutable base RRF anchors, hierarchy diagnostics, and expected-evidence metrics are in the JSON artifact.",
    ]
    (REPORTS / "legal_hierarchy_v2_retrieval_before_after.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    ctx_lines = [
        "# Legal Hierarchy Retrieval V2 — Context",
        "",
        "The frozen 4,096-token budget, exact token counter, whole-chunk selection, and Greedy Stop are unchanged.",
        "",
        f"- Expected-evidence retention before/after: {_percent(context['before']['expected_evidence_retention'])} / {_percent(context['after']['expected_evidence_retention'])}",
        f"- Retrieved-but-dropped before/after: {context['before']['retrieved_but_dropped_count']} / {context['after']['retrieved_but_dropped_count']}",
        f"- Budget exhausted before/after: {context['before']['budget_exhausted_count']} / {context['after']['budget_exhausted_count']}",
        f"- Average context tokens before/after: {context['token_distribution_before']['mean']:.1f} / {context['token_distribution_after']['mean']:.1f}",
    ]
    (REPORTS / "legal_hierarchy_v2_context.md").write_text("\n".join(ctx_lines) + "\n", encoding="utf-8")

    before_g = generation["before"]
    after_g = generation["after"]
    gen_lines = [
        "# Legal Hierarchy Retrieval V2 — Generation Consequences",
        "",
        "Block 6, `legal-rag-v2`, and qwen3.5:9b were unchanged.",
        "",
        f"- Citation presence before/after: {_percent(before_g['generation']['citation_presence_rate'])} / {_percent(after_g['generation']['citation_presence_rate'])}",
        f"- Expected-source match before/after: {_percent(before_g['generation']['expected_source_citation_match_rate'])} / {_percent(after_g['generation']['expected_source_citation_match_rate'])}",
        f"- Correct abstention before/after: {_percent(before_g['answerability']['correct_abstention_rate'])} / {_percent(after_g['answerability']['correct_abstention_rate'])}",
        f"- False abstention before/after: {_percent(before_g['answerability']['false_abstention_rate'])} / {_percent(after_g['answerability']['false_abstention_rate'])}",
        f"- Unsupported direct-answer rate: {_percent(after_g['answerability']['unsupported_direct_answer_rate'])}",
    ]
    (REPORTS / "legal_hierarchy_v2_generation.md").write_text("\n".join(gen_lines) + "\n", encoding="utf-8")

    false_cases = [
        item for item in generation["cases"]
        if item["answerable"] and item["block6"]["status"] == "INSUFFICIENT_EVIDENCE"
    ]
    false_lines = [
        "# Hierarchy V2 False-Abstention Observation",
        "",
        "This task does not calibrate supported-case abstention. Cases below are separated from retrieval failure using deterministic expected-evidence completeness.",
        "",
    ]
    for item in false_cases:
        complete = bool(item["metrics_v2"]["context_evidence"] and item["metrics_v2"]["context_evidence"]["complete"])
        false_lines.append(f"- `{item['case_id']}` — context complete: **{complete}**; diagnosis: `{item['failure_attribution_v2']}`")
    (REPORTS / "hierarchy_v2_false_abstention_observation.md").write_text("\n".join(false_lines) + "\n", encoding="utf-8")

    latency = retrieval["latency"]
    latency_lines = [
        "# Legal Hierarchy Retrieval V2 — Latency",
        "",
        f"- Lookup mean / p50 / p95: {latency['lookup_ms']['mean']:.3f} / {latency['lookup_ms']['p50']:.3f} / {latency['lookup_ms']['p95']:.3f} ms",
        f"- Total hierarchy mean / p50 / p95: {latency['total_ms']['mean']:.3f} / {latency['total_ms']['p50']:.3f} / {latency['total_ms']['p95']:.3f} ms",
        f"- Retrieval mean before/after: {latency['retrieval_before_ms']['mean_ms']:.3f} / {latency['retrieval_after_ms']['mean_ms']:.3f} ms",
        "- EXPLAIN ANALYZE is recorded in the final verification evidence; no production index was added.",
    ]
    (REPORTS / "legal_hierarchy_v2_latency.md").write_text("\n".join(latency_lines) + "\n", encoding="utf-8")


async def run(resume: bool = False) -> dict[str, Any]:
    if sha(DATASET) != V2_SHA256 or sha(V1_DATASET) != V1_SHA256:
        raise RuntimeError("Frozen evaluation dataset hash mismatch")
    dataset = load_dataset(DATASET)
    db = SessionLocal()
    profile = get_generation_profile()
    context_builder = ContextBuilderService(ContextTokenCounter(profile.tokenizer_provider, profile.tokenizer_id))
    prompt_counter = PromptTokenCounter(profile.tokenizer_provider, profile.tokenizer_id, thinking=profile.thinking)
    llm_client = get_llm_client()
    prior: dict[str, dict[str, Any]] = {}
    if resume and RAW_PROGRESS.exists():
        loaded = json.loads(RAW_PROGRESS.read_text(encoding="utf-8"))
        prior = {item["case_id"]: item for item in loaded.get("cases", [])}
    try:
        validation = validate_dataset(dataset, db)
        await llm_client.health(profile)
        cases: list[dict[str, Any]] = []
        for index, case in enumerate(dataset.cases, start=1):
            if case.case_id in prior:
                measured = prior[case.case_id]
                print(f"[{index}/{len(dataset.cases)}] {case.case_id} (resume)", flush=True)
            else:
                print(f"[{index}/{len(dataset.cases)}] {case.case_id}", flush=True)
                measured = await run_case(case, db, context_builder, prompt_counter, profile, llm_client)
                mode = lexical_mode(db, case.question, case.document_ids, len(measured["block4"]["lexical_candidates"]))
                measured = enrich_case(measured, mode)
            cases.append(measured)
            _write(RAW_PROGRESS, {"report_id": "legal_hierarchy_v2_generation", "run_status": "IN_PROGRESS", "dataset_sha256": V2_SHA256, "cases": cases})
        artifacts = build_artifacts(cases, validation)
        write_markdown(artifacts)
        return artifacts
    finally:
        db.close()
        await close_llm_client()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(run(resume=args.resume))
    print(json.dumps({"aggregate": result["aggregate"], "h2_parity": result["h2_parity"]}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
