"""Run the paired P0/P1 Legal-RAG-V3 final ablation with the real provider."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import statistics
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from app.context.service import ContextBuilderService
from app.generation.profile import get_generation_profile
from app.generation.prompting import load_system_prompt
from app.generation.runtime import close_llm_client, get_llm_client
from app.generation.tokenizers import ContextTokenCounter, PromptTokenCounter
from evaluation.experiments.evidence_presentation_v1.presentation import (
    PRESENTATIONS,
    apply_presentation,
)
from evaluation.experiments.evidence_presentation_v1.runner import (
    build_package,
    category_breakdown,
    fingerprint,
    generate_once,
    mean,
    production_files,
    sha256,
    summarize,
    write_json,
    write_text,
)


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
REPORTS = ROOT / "evaluation" / "reports"
DATASET_V1 = ROOT / "evaluation" / "datasets" / "legal_eval_v1.json"
DATASET_V2 = ROOT / "evaluation" / "datasets" / "legal_eval_v2.json"
HIERARCHY_REPORT = REPORTS / "legal_hierarchy_v2_generation.json"
PREVIOUS_EXPERIMENT = ROOT / "evaluation" / "experiments" / "evidence_presentation_v1" / "experiment_results.json"
PROMPT_PATH = ROOT / "evaluation" / "experiments" / "evidence_presentation_v1" / "legal-rag-v3-compact-fewshot-experimental.txt"
PROGRESS = HERE / "raw_progress.json"
FINAL_JSON = HERE / "experiment_results.json"
REPORT_JSON = REPORTS / "legal_rag_v3_final_ablation_v1.json"
REPORT_MD = REPORTS / "legal_rag_v3_final_ablation_v1.md"

V1_SHA256 = "afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245"
V2_SHA256 = "ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842"
PROMPT_SHA256 = "cb43cd1998e857f232b8eb998a7021d51d68a6da74f91399c103fd2e577a6af1"
VARIANTS = {"A": "P0", "B": "P1"}
FALSE_CASE_IDS = (
    "v2_bank_scope_ratios",
    "v2_bank_below_80_measures",
    "v2_civil_scope",
    "v2_cross_document_effective_dates",
)


class ProgressStore:
    def __init__(self, fresh: bool):
        if fresh and PROGRESS.exists():
            PROGRESS.unlink()
        self.records: dict[str, dict[str, Any]] = {}
        if PROGRESS.exists():
            data = json.loads(PROGRESS.read_text(encoding="utf-8"))
            self.records = {
                item.get("checkpoint_key", item["key"]): item
                for item in data.get("records", [])
            }

    def save(self) -> None:
        payload = {
            "experiment": "legal-rag-v3-final-ablation-design-gate",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "records": list(self.records.values()),
        }
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        temporary = PROGRESS.with_suffix(".json.tmp")
        last_error: OSError | None = None
        for attempt in range(5):
            try:
                temporary.write_text(serialized, encoding="utf-8")
                os.replace(temporary, PROGRESS)
                return
            except OSError as exc:
                last_error = exc
                time.sleep(0.1 * (attempt + 1))
        assert last_error is not None
        raise last_error

    async def ensure(self, key: str, factory: Callable) -> dict[str, Any]:
        if key in self.records:
            print(f"[resume] {key}", flush=True)
            return self.records[key]
        print(f"[run] {key}", flush=True)
        started = perf_counter()
        record = await factory()
        record["experiment_total_ms"] = (perf_counter() - started) * 1000
        record["checkpoint_key"] = key
        self.records[key] = record
        self.save()
        return record


def exact_mcnemar_pvalue(b_gains: int, b_losses: int) -> float:
    """Two-sided exact McNemar/binomial p-value for paired binary outcomes."""
    discordant = b_gains + b_losses
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, index) for index in range(min(b_gains, b_losses) + 1))
    return min(1.0, 2.0 * tail / (2**discordant))


def paired_outcome(
    records_a: list[dict[str, Any]], records_b: list[dict[str, Any]], field: str
) -> dict[str, Any]:
    by_a = {item["case_id"]: bool(item[field]) for item in records_a}
    by_b = {item["case_id"]: bool(item[field]) for item in records_b}
    if set(by_a) != set(by_b):
        raise RuntimeError(f"paired record mismatch for {field}")
    gains = [case_id for case_id in by_a if not by_a[case_id] and by_b[case_id]]
    losses = [case_id for case_id in by_a if by_a[case_id] and not by_b[case_id]]
    same_positive = [case_id for case_id in by_a if by_a[case_id] and by_b[case_id]]
    same_negative = [case_id for case_id in by_a if not by_a[case_id] and not by_b[case_id]]
    return {
        "p1_gains": gains,
        "p1_losses": losses,
        "same_positive": same_positive,
        "same_negative": same_negative,
        "net_gain": len(gains) - len(losses),
        "mcnemar_exact_pvalue": exact_mcnemar_pvalue(len(gains), len(losses)),
    }


def marker_contract(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "run_count": len(records),
        "valid_count": sum(item["answerability_validation"] == "PASS" for item in records),
        "exactly_one_marker_count": sum(item["raw_status_marker_count"] == 1 for item in records),
        "duplicate_count": sum(item["raw_status_marker_count"] > 1 for item in records),
        "missing_or_malformed_count": sum(
            item["answerability_validation"] != "PASS" and item["raw_status_marker_count"] <= 1
            for item in records
        ),
    }


def targeted_by_case(records: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for case_id in FALSE_CASE_IDS:
        items = [item for item in records if item["case_id"] == case_id]
        result[case_id] = {
            "runs": len(items),
            "answerable": sum(item["answerability_status"] == "ANSWERABLE" for item in items),
            "insufficient": sum(item["answerability_status"] == "INSUFFICIENT_EVIDENCE" for item in items),
            "grounded": sum(item["grounded_conversion"] for item in items),
            "citation_valid": sum(
                bool(item["mapped_chunk_ids"]) and item["citation_validation"] == "PASS"
                for item in items
            ),
            "expected_source": sum(item["expected_source_complete"] is True for item in items),
            "status_valid": sum(item["answerability_validation"] == "PASS" for item in items),
            "records": items,
        }
    return result


def comparable_latency(
    records: list[dict[str, Any]], by_id: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    totals = []
    for item in records:
        frozen = by_id[item["case_id"]]["timings"]
        totals.append(
            float(frozen.get("retrieval_ms") or 0)
            + float(frozen.get("context_ms") or 0)
            + float(item["experiment_total_ms"])
        )
    return {
        "run_count": len(records),
        "mean_prompt_tokens": mean([item["prompt_tokens"] for item in records]),
        "mean_context_tokens": mean([item["context_tokens"] for item in records]),
        "mean_ttft_ms": mean([item["ttft_ms"] for item in records]),
        "mean_generation_ms": mean([item["generation_ms"] for item in records]),
        "mean_experiment_total_ms": mean([item["experiment_total_ms"] for item in records]),
        "mean_comparable_pipeline_total_ms": mean(totals),
        "method": "frozen retrieval_ms + frozen context_ms + measured prompt/provider experiment total",
    }


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.2f}%"


def render_report(result: dict[str, Any]) -> None:
    a = result["variants"]["A"]
    b = result["variants"]["B"]
    gate = result["design_gate"]
    lines = [
        "# Legal-RAG-V3 Final Ablation + Design Gate",
        "",
        "## Frozen state",
        "",
        f"- Evaluation V1 SHA-256: `{result['datasets']['evaluation_v1']}`",
        f"- Evaluation V2 SHA-256: `{result['datasets']['evaluation_v2']}`",
        f"- Experimental prompt SHA-256: `{result['prompt']['sha256']}`",
        "- Production prompt: `legal-rag-v2`",
        "- Production changed: **NO**",
        "",
        "## P0 versus P1",
        "",
        "| Variant | Acceptance | False abstention | Citation presence | Citation validity | Expected source | Status validity |",
        "|---|---:|---:|---:|---:|---:|---:|",
        f"| A: compact few-shot + P0 | {pct(a['full_answerable']['answerable_acceptance_rate'])} | {pct(a['full_answerable']['false_abstention_rate'])} | {pct(a['full_answerable']['citation_presence_rate'])} | {pct(a['full_answerable']['citation_validity_rate'])} | {pct(a['full_answerable']['expected_source_match_rate'])} | {pct(a['full_answerable']['status_valid_rate'])} |",
        f"| B: compact few-shot + P1 | {pct(b['full_answerable']['answerable_acceptance_rate'])} | {pct(b['full_answerable']['false_abstention_rate'])} | {pct(b['full_answerable']['citation_presence_rate'])} | {pct(b['full_answerable']['citation_validity_rate'])} | {pct(b['full_answerable']['expected_source_match_rate'])} | {pct(b['full_answerable']['status_valid_rate'])} |",
        "",
        f"P1 materially beneficial: **{'YES' if result['p1_necessity']['materially_beneficial'] else 'NO'}**.",
        "",
        result["p1_necessity"]["rationale"],
        "",
        "## Targeted 5-run repeatability",
        "",
        "| Case | A answerable/grounded | B answerable/grounded | A/B status valid |",
        "|---|---:|---:|---:|",
    ]
    for case_id in FALSE_CASE_IDS:
        ca = a["targeted_by_case"][case_id]
        cb = b["targeted_by_case"][case_id]
        lines.append(
            f"| `{case_id}` | {ca['answerable']}/5, {ca['grounded']}/5 | {cb['answerable']}/5, {cb['grounded']}/5 | {ca['status_valid']}/5, {cb['status_valid']}/5 |"
        )
    lines.extend([
        "",
        "## Repeated safety",
        "",
        f"- Runs: {a['safety']['run_count']} A + {b['safety']['run_count']} B = {a['safety']['run_count'] + b['safety']['run_count']}",
        f"- Correct structured abstentions: {a['safety_correct_abstentions'] + b['safety_correct_abstentions']}/{a['safety']['run_count'] + b['safety']['run_count']}",
        f"- Unsupported direct answers: {a['safety']['unsupported_direct_answer_count'] + b['safety']['unsupported_direct_answer_count']}",
        f"- Status failures: {(a['safety']['run_count'] - a['safety_marker_contract']['valid_count']) + (b['safety']['run_count'] - b['safety_marker_contract']['valid_count'])}",
        "",
        "## Multi-evidence breakdown",
        "",
        "| Class | A grounded | B grounded |",
        "|---|---:|---:|",
    ])
    for label in ("single_evidence", "multi_evidence", "hierarchy_recovered", "multi_document"):
        lines.append(
            f"| {label} | {pct(a['category_breakdown'][label]['grounded_conversion_rate'])} | {pct(b['category_breakdown'][label]['grounded_conversion_rate'])} |"
        )
    lines.extend([
        "",
        "## Civil scope",
        "",
        f"- A: {a['targeted_by_case']['v2_civil_scope']['grounded']}/5 grounded",
        f"- B: {b['targeted_by_case']['v2_civil_scope']['grounded']}/5 grounded",
        f"- Resolved: **{'YES' if result['civil_scope']['resolved'] else 'NO'}**",
        f"- Future Context Selection V2 candidate: **{'YES' if result['civil_scope']['future_context_selection_v2_candidate'] else 'NO'}**",
        "",
        "## Token and latency comparison",
        "",
        "| Configuration | Prompt tokens | TTFT ms | Generation ms | Comparable total ms |",
        "|---|---:|---:|---:|---:|",
        f"| production legal-rag-v2 | {result['production_comparison']['mean_prompt_tokens']:.1f} | {result['production_comparison']['mean_ttft_ms']:.1f} | {result['production_comparison']['mean_generation_ms']:.1f} | {result['production_comparison']['mean_total_ms']:.1f} |",
        f"| A: compact few-shot + P0 | {a['latency']['mean_prompt_tokens']:.1f} | {a['latency']['mean_ttft_ms']:.1f} | {a['latency']['mean_generation_ms']:.1f} | {a['latency']['mean_comparable_pipeline_total_ms']:.1f} |",
        f"| B: compact few-shot + P1 | {b['latency']['mean_prompt_tokens']:.1f} | {b['latency']['mean_ttft_ms']:.1f} | {b['latency']['mean_generation_ms']:.1f} | {b['latency']['mean_comparable_pipeline_total_ms']:.1f} |",
        "",
        "A/B comparable totals reuse the identical frozen retrieval/context timings and add the newly measured prompt/provider elapsed time; they are diagnostics, not an SLA.",
        "",
        "## Design gate",
        "",
        f"- Candidate: **{gate['candidate']}**",
        f"- Gate pass: **{'YES' if gate['pass'] else 'NO'}**",
        f"- Next target: **{gate['next_target']}**",
        "",
        gate["reason"],
        "",
        "The experimental prompt remains isolated. GenerationProfile still selects `legal-rag-v2`.",
    ])
    write_text(REPORT_MD, "\n".join(lines))


async def run(fresh: bool = False) -> dict[str, Any]:
    hashes = {"evaluation_v1": sha256(DATASET_V1), "evaluation_v2": sha256(DATASET_V2)}
    if hashes != {"evaluation_v1": V1_SHA256, "evaluation_v2": V2_SHA256}:
        raise RuntimeError(f"Frozen dataset hash mismatch: {hashes}")
    if sha256(PROMPT_PATH) != PROMPT_SHA256:
        raise RuntimeError("Exact compact-fewshot experimental prompt hash changed")

    source = json.loads(HIERARCHY_REPORT.read_text(encoding="utf-8"))
    cases = source["cases"]
    if len(cases) != 65:
        raise RuntimeError("Expected 65 frozen Evaluation V2 cases")
    by_id = {item["case_id"]: item for item in cases}
    answerable = [item for item in cases if item["answerable"]]
    unanswerable = [item for item in cases if not item["answerable"]]
    targeted = [by_id[item] for item in FALSE_CASE_IDS]
    if len(answerable) != 55 or len(unanswerable) != 10:
        raise RuntimeError("Frozen V2 answerable/safety counts changed")

    profile = get_generation_profile()
    if profile.prompt_version != "legal-rag-v2" or profile.model_id != "qwen3.5:9b":
        raise RuntimeError("Production profile drifted from legal-rag-v2/qwen3.5:9b")
    if load_system_prompt("legal-rag-v2") != (ROOT / "app" / "prompts" / "legal-rag-v2.txt").read_text(encoding="utf-8").strip():
        raise RuntimeError("Production prompt loader mismatch")

    context_counter = ContextTokenCounter(profile.tokenizer_provider, profile.tokenizer_id)
    prompt_counter = PromptTokenCounter(profile.tokenizer_provider, profile.tokenizer_id, thinking=profile.thinking)
    builder = ContextBuilderService(context_counter)
    prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()
    base_packages = {item["case_id"]: build_package(item, builder, profile) for item in cases}
    packages: dict[tuple[str, str], Any] = {}
    transform_ms: dict[str, list[float]] = {"A": [], "B": []}
    for variant, presentation_key in VARIANTS.items():
        spec = PRESENTATIONS[presentation_key]
        for item in cases:
            started = perf_counter()
            package = apply_presentation(base_packages[item["case_id"]], spec, context_counter)
            transform_ms[variant].append((perf_counter() - started) * 1000)
            if {e.chunk_id for e in package.selected_evidence} != set(item["block5"]["selected_chunk_ids"]):
                raise RuntimeError(f"{variant}/{item['case_id']} changed selected evidence")
            packages[(variant, item["case_id"])] = package

    store = ProgressStore(fresh)
    client = get_llm_client()
    await client.health(profile)

    async def one(case: dict[str, Any], variant: str, run_index: int, purpose: str) -> dict[str, Any]:
        pkey = VARIANTS[variant]
        key = f"{purpose}|{variant}|{pkey}|{case['case_id']}|{run_index}"
        return await store.ensure(key, lambda: generate_once(
            case=case,
            package=packages[(variant, case["case_id"])],
            prompt_label="compact-fewshot",
            prompt=prompt,
            presentation=PRESENTATIONS[pkey],
            run_index=run_index,
            purpose=f"{purpose}-{variant}",
            profile=profile,
            context_counter=context_counter,
            prompt_counter=prompt_counter,
            client=client,
        ))

    targeted_records: dict[str, list[dict[str, Any]]] = {}
    full_records: dict[str, list[dict[str, Any]]] = {}
    safety_records: dict[str, list[dict[str, Any]]] = {}
    for variant in VARIANTS:
        targeted_records[variant] = [
            await one(case, variant, repeat, "targeted-5x")
            for case in targeted for repeat in range(1, 6)
        ]
        full_records[variant] = [
            await one(case, variant, 1, "full-answerable") for case in answerable
        ]
        safety_records[variant] = [
            await one(case, variant, repeat, "safety-3x")
            for case in unanswerable for repeat in range(1, 4)
        ]

    previous = json.loads(PREVIOUS_EXPERIMENT.read_text(encoding="utf-8"))
    production = previous["frozen_evaluation_baseline"]

    variant_results: dict[str, Any] = {}
    for variant in VARIANTS:
        first_safety = [item for item in safety_records[variant] if item["run_index"] == 1]
        comparable = full_records[variant] + first_safety
        hard = [item for item in safety_records[variant] if item["category"] == "HARD_UNANSWERABLE"]
        out = [item for item in safety_records[variant] if item["category"] == "OUT_OF_CORPUS"]
        partial_answerable = [item for item in targeted_records[variant] + full_records[variant] if item["category"] == "PARTIAL_SUPPORT"]
        variant_results[variant] = {
            "presentation": VARIANTS[variant],
            "targeted": summarize(targeted_records[variant], answerable=True),
            "targeted_by_case": targeted_by_case(targeted_records[variant]),
            "full_answerable": summarize(full_records[variant], answerable=True),
            "full_answerable_records": full_records[variant],
            "category_breakdown": category_breakdown(full_records[variant], cases),
            "safety": summarize(safety_records[variant], answerable=False),
            "safety_correct_abstentions": sum(item["answerability_status"] == "INSUFFICIENT_EVIDENCE" for item in safety_records[variant]),
            "safety_marker_contract": marker_contract(safety_records[variant]),
            "hard_unanswerable": summarize(hard, answerable=False),
            "out_of_corpus": summarize(out, answerable=False),
            "safety_records": safety_records[variant],
            "partial_support_qualified_answer": {
                "case_ids": sorted({item["case_id"] for item in partial_answerable}),
                "run_count": len(partial_answerable),
                "answerable_count": sum(item["answerability_status"] == "ANSWERABLE" for item in partial_answerable),
                "grounded_count": sum(item["grounded_conversion"] for item in partial_answerable),
                "status_valid_count": sum(item["answerability_validation"] == "PASS" for item in partial_answerable),
            },
            "all_marker_contract": marker_contract(targeted_records[variant] + full_records[variant] + safety_records[variant]),
            "latency": comparable_latency(comparable, by_id),
            "mean_presentation_transform_ms": statistics.fmean(transform_ms[variant]),
        }

    paired = {
        "answerable": paired_outcome(full_records["A"], full_records["B"], "answerability_status"),
        "grounded": paired_outcome(full_records["A"], full_records["B"], "grounded_conversion"),
        "expected_source": paired_outcome(full_records["A"], full_records["B"], "expected_source_complete"),
    }
    # answerability_status is a non-empty string for both statuses, so replace
    # that paired result with the actual ANSWERABLE predicate.
    paired_answerable_a = [{**item, "accepted": item["answerability_status"] == "ANSWERABLE"} for item in full_records["A"]]
    paired_answerable_b = [{**item, "accepted": item["answerability_status"] == "ANSWERABLE"} for item in full_records["B"]]
    paired["answerable"] = paired_outcome(paired_answerable_a, paired_answerable_b, "accepted")

    a_full = variant_results["A"]["full_answerable"]
    b_full = variant_results["B"]["full_answerable"]
    a_target = variant_results["A"]["targeted"]
    b_target = variant_results["B"]["targeted"]
    full_net_grounded = paired["grounded"]["net_gain"]
    targeted_grounded_delta = (b_target["grounded_conversion_rate"] or 0) - (a_target["grounded_conversion_rate"] or 0)
    p1_material = bool(
        full_net_grounded >= 2
        and targeted_grounded_delta >= 0.10
        and variant_results["B"]["safety"]["abstention_rate"] == 1.0
        and variant_results["B"]["safety"]["status_valid_rate"] == 1.0
        and (b_full["citation_validity_rate"] or 0) >= (a_full["citation_validity_rate"] or 0)
        and (b_full["expected_source_match_rate"] or 0) >= (a_full["expected_source_match_rate"] or 0)
    )
    practically_equivalent = bool(
        abs((b_full["false_abstention_rate"] or 0) - (a_full["false_abstention_rate"] or 0)) <= 1 / 55
        and abs((b_full["citation_validity_rate"] or 0) - (a_full["citation_validity_rate"] or 0)) <= 1 / 55
        and abs((b_full["expected_source_match_rate"] or 0) - (a_full["expected_source_match_rate"] or 0)) <= 1 / 55
        and abs(targeted_grounded_delta) <= 1 / 20
    )
    p1_rationale = (
        "P1 produced a repeatable net gain of at least two full-corpus grounded cases and at least 10 percentage points on the 20 targeted repeats without safety, status, citation, or expected-source regression."
        if p1_material else
        "P1 did not meet the predeclared material-benefit rule (>=2 net full-corpus grounded gains plus >=10 targeted percentage points with no quality regression). The prompt-only P0 candidate is the smaller architecture change."
    )

    civil_a = variant_results["A"]["targeted_by_case"]["v2_civil_scope"]
    civil_b = variant_results["B"]["targeted_by_case"]["v2_civil_scope"]
    civil_resolved = civil_a["grounded"] > 0 or civil_b["grounded"] > 0

    candidate_variant = "B" if p1_material else "A"
    candidate = variant_results[candidate_variant]
    full_candidate = candidate["full_answerable"]
    safety_candidate = candidate["safety"]
    gate_checks = {
        "material_false_abstention_reduction": (full_candidate["false_abstention_rate"] or 1) < production["false_abstention_rate"],
        "unanswerable_safety_100_percent": safety_candidate["abstention_rate"] == 1.0,
        "unsupported_direct_answers_zero": safety_candidate["unsupported_direct_answer_count"] == 0,
        "status_validity_100_percent": candidate["all_marker_contract"]["valid_count"] == candidate["all_marker_contract"]["run_count"],
        "citation_validity_preserved": (full_candidate["citation_validity_rate"] or 0) >= production["citation_validity_rate"],
        "expected_source_preserved": (full_candidate["expected_source_match_rate"] or 0) >= production["expected_source_match_rate"],
        "second_llm_absent": True,
        "semantic_status_inference_absent": True,
        "ground_truth_runtime_dependency_absent": True,
    }
    gate_pass = all(gate_checks.values())
    candidate_name = "LEGAL-RAG-V3 + P1" if candidate_variant == "B" else "PROMPT-ONLY LEGAL-RAG-V3"
    next_target = "LEGAL-RAG-V3 DESIGN" if gate_pass else ("CONTEXT SELECTION V2 EXPERIMENT" if not civil_resolved else "MORE DATA")

    result = {
        "experiment_id": "legal-rag-v3-final-ablation-design-gate",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "datasets": hashes,
        "prompt": fingerprint(PROMPT_PATH),
        "production_prompt": "legal-rag-v2",
        "production_changed": False,
        "configuration": {
            "provider": profile.provider,
            "model_id": profile.model_id,
            "tokenizer_provider": profile.tokenizer_provider,
            "tokenizer_id": profile.tokenizer_id,
            "temperature": profile.temperature,
            "top_p": profile.top_p,
            "top_k": profile.top_k,
            "thinking": profile.thinking,
            "context_budget_tokens": profile.context_budget_tokens,
            "max_output_tokens": profile.max_output_tokens,
            "prompt_token_safety_margin": profile.prompt_token_safety_margin,
            "production_prompt_version": profile.prompt_version,
            "status_parser_changed": False,
            "citation_parser_changed": False,
        },
        "production_file_fingerprints": [fingerprint(path) for path in production_files()],
        "production_comparison": {
            "answerable_acceptance_rate": production["answerable_acceptance_rate"],
            "false_abstention_rate": production["false_abstention_rate"],
            "citation_validity_rate": production["citation_validity_rate"],
            "expected_source_match_rate": production["expected_source_match_rate"],
            "mean_prompt_tokens": production["mean_prompt_tokens"],
            "mean_ttft_ms": production["mean_ttft_ms"],
            "mean_generation_ms": production["mean_generation_ms"],
            "mean_total_ms": production["mean_total_ms"],
        },
        "variants": variant_results,
        "paired_comparison": paired,
        "p1_necessity": {
            "materially_beneficial": p1_material,
            "practically_equivalent_under_one_case_margin": practically_equivalent,
            "targeted_grounded_rate_delta": targeted_grounded_delta,
            "full_grounded_net_gain": full_net_grounded,
            "rule": "P1 material only with >=2 net full grounded gains and >=10 targeted percentage points, with no safety/status/citation/expected-source regression",
            "rationale": p1_rationale,
            "additional_contract_impact": "P1 would amend Block 5 model-facing evidence formatting; P0 requires no Block 5 amendment.",
        },
        "civil_scope": {
            "resolved": civil_resolved,
            "variant_a_grounded_runs": civil_a["grounded"],
            "variant_b_grounded_runs": civil_b["grounded"],
            "future_context_selection_v2_candidate": not civil_resolved,
            "prompt_should_not_be_weakened_for_single_case": not civil_resolved,
        },
        "design_gate": {
            "candidate": candidate_name if gate_pass else "NO CHANGE",
            "selected_variant": candidate_variant if gate_pass else None,
            "checks": gate_checks,
            "pass": gate_pass,
            "next_target": next_target,
            "reason": (
                f"{candidate_name} passes all nine design-gate criteria. "
                + ("P1 is excluded because it did not demonstrate a clear repeatable benefit sufficient to justify a Block 5 presentation-contract amendment." if candidate_variant == "A" else "P1 demonstrated a clear repeatable benefit sufficient to justify documenting its additional Block 5 presentation contract.")
                if gate_pass else
                "No candidate passed every frozen safety, status, citation, expected-source, and architecture criterion."
            ),
            "production_implementation_authorized": False,
        },
        "method_limits": [
            "Full answerable evaluation uses one new real generation per case per variant; targeted cases use five and safety cases use three.",
            "Expected-source matching is deterministic and is not semantic entailment proof.",
            "The frozen corpus contains only ten unanswerable cases.",
            "Comparable A/B total latency reuses frozen retrieval/context timings because the ablation intentionally holds selected context fixed.",
        ],
    }
    write_json(FINAL_JSON, result)
    write_json(REPORT_JSON, result)
    render_report(result)
    return result


async def run_and_close(fresh: bool) -> dict[str, Any]:
    try:
        return await run(fresh)
    finally:
        await close_llm_client()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(run_and_close(args.fresh))
    print(json.dumps({
        "p1_necessity": result["p1_necessity"],
        "design_gate": result["design_gate"],
    }, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
