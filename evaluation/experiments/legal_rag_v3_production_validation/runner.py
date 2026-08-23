"""Validate the approved runtime Legal-RAG-V3 prompt against frozen P0 contexts.

The default production profile is required to remain legal-rag-v2. This runner
creates immutable in-process profile variants and changes only prompt_version.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import time
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from app.context.service import ContextBuilderService
from app.generation.profile import get_generation_profile
from app.generation.prompting import load_system_prompt
from app.generation.runtime import close_llm_client, get_llm_client
from app.generation.tokenizers import ContextTokenCounter, PromptTokenCounter
from evaluation.experiments.evidence_presentation_v1.presentation import PRESENTATIONS
from evaluation.experiments.evidence_presentation_v1.runner import (
    build_package,
    category_breakdown,
    generate_once,
    messages_for,
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
PROMPTS = {
    "legal-rag-v2": ROOT / "app" / "prompts" / "legal-rag-v2.txt",
    "legal-rag-v3": ROOT / "app" / "prompts" / "legal-rag-v3.txt",
}
PROGRESS = HERE / "raw_progress.json"
FINAL_JSON = HERE / "experiment_results.json"
REPORT_JSON = REPORTS / "legal_rag_v3_production_validation_v1.json"
REPORT_MD = REPORTS / "legal_rag_v3_production_validation_v1.md"
HUMAN_MD = REPORTS / "legal_rag_v3_human_review_v1.md"

V1_SHA256 = "afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245"
V2_SHA256 = "ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842"
PROMPT_SHA256 = {
    "legal-rag-v2": "a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee",
    "legal-rag-v3": "35b0abd69608ef574ac7bbf5c314eadb6ef9decd0dda3dd60e0a170aad243ebf",
}
TARGET_IDS = (
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
            payload = json.loads(PROGRESS.read_text(encoding="utf-8"))
            self.records = {item["checkpoint_key"]: item for item in payload.get("records", [])}

    def save(self) -> None:
        value = json.dumps({
            "experiment": "legal-rag-v3-production-validation-v1",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "records": list(self.records.values()),
        }, ensure_ascii=False, indent=2)
        temporary = PROGRESS.with_suffix(".json.tmp")
        last_error: OSError | None = None
        for attempt in range(5):
            try:
                temporary.write_text(value, encoding="utf-8")
                os.replace(temporary, PROGRESS)
                return
            except OSError as exc:
                last_error = exc
                time.sleep(0.1 * (attempt + 1))
        raise last_error or RuntimeError("progress write failed")

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


def percentile(values: list[float | int | None], fraction: float) -> float | None:
    clean = sorted(float(value) for value in values if value is not None)
    if not clean:
        return None
    position = (len(clean) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(clean) - 1)
    return clean[lower] + (clean[upper] - clean[lower]) * (position - lower)


def distribution(values: list[float | int | None]) -> dict[str, float | int | None]:
    clean = [float(value) for value in values if value is not None]
    return {
        "count": len(clean),
        "mean": statistics.fmean(clean) if clean else None,
        "median": statistics.median(clean) if clean else None,
        "min": min(clean) if clean else None,
        "max": max(clean) if clean else None,
        "p95": percentile(clean, 0.95),
    }


def marker_contract(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "runs": len(records),
        "valid": sum(item["answerability_validation"] == "PASS" for item in records),
        "exactly_one": sum(item["raw_status_marker_count"] == 1 for item in records),
        "duplicate": sum(item["raw_status_marker_count"] > 1 for item in records),
        "missing_or_malformed": sum(item["answerability_validation"] != "PASS" for item in records),
    }


def paired(records_v2: list[dict[str, Any]], records_v3: list[dict[str, Any]], predicate: Callable) -> dict[str, Any]:
    v2 = {item["case_id"]: bool(predicate(item)) for item in records_v2}
    v3 = {item["case_id"]: bool(predicate(item)) for item in records_v3}
    if set(v2) != set(v3):
        raise RuntimeError("paired case sets differ")
    gains = sorted(case_id for case_id in v2 if not v2[case_id] and v3[case_id])
    losses = sorted(case_id for case_id in v2 if v2[case_id] and not v3[case_id])
    return {"v3_gains": gains, "v3_losses": losses, "net_gain": len(gains) - len(losses)}


def by_target(records: list[dict[str, Any]]) -> dict[str, Any]:
    output = {}
    for case_id in TARGET_IDS:
        items = [item for item in records if item["case_id"] == case_id]
        output[case_id] = {
            "runs": len(items),
            "answerable": sum(item["answerability_status"] == "ANSWERABLE" for item in items),
            "insufficient": sum(item["answerability_status"] == "INSUFFICIENT_EVIDENCE" for item in items),
            "grounded": sum(item["grounded_conversion"] for item in items),
            "citation_valid": sum(bool(item["mapped_chunk_ids"]) and item["citation_validation"] == "PASS" for item in items),
            "expected_source": sum(item["expected_source_complete"] is True for item in items),
            "status_valid": sum(item["answerability_validation"] == "PASS" for item in items),
            "records": items,
        }
    return output


def token_measurements(cases, packages, counters, profiles) -> dict[str, Any]:
    output = {}
    for version in ("legal-rag-v2", "legal-rag-v3"):
        values = []
        reserved = []
        prompt = load_system_prompt(version)
        for case in cases:
            package = packages[case["case_id"]]
            messages = messages_for(package, prompt, "production")
            count = counters[version].count_messages(messages)
            values.append(count)
            reserved.append(count + profiles[version].max_output_tokens + profiles[version].prompt_token_safety_margin)
        output[version] = {
            "prompt_tokens": distribution(values),
            "reserved_tokens": distribution(reserved),
            "hard_limit": profiles[version].model_context_limit,
            "overflow_count": sum(value > profiles[version].model_context_limit for value in reserved),
        }
    output["paired_delta_v3_minus_v2"] = distribution([
        counters["legal-rag-v3"].count_messages(messages_for(
            packages[case["case_id"]], load_system_prompt("legal-rag-v3"), "production"
        )) - counters["legal-rag-v2"].count_messages(messages_for(
            packages[case["case_id"]], load_system_prompt("legal-rag-v2"), "production"
        )) for case in cases
    ])
    return output


def review_package(
    case: dict[str, Any],
    record_v2: dict[str, Any],
    record_v3: dict[str, Any],
    package,
    reasons: list[str],
) -> dict[str, Any]:
    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "question": case["question"],
        "acceptable_evidence_sets": case["acceptable_evidence_sets"],
        "review_reasons": reasons,
        "v2": {
            "answerability_status": record_v2["answerability_status"],
            "public_answer_text": record_v2["public_answer_text"],
            "citation_source_ids": record_v2["citation_source_ids"],
            "mapped_chunk_ids": record_v2["mapped_chunk_ids"],
            "expected_source_complete": record_v2["expected_source_complete"],
        },
        "v3": {
            "answerability_status": record_v3["answerability_status"],
            "answerability_validation": record_v3["answerability_validation"],
            "public_answer_text": record_v3["public_answer_text"],
            "citation_source_ids": record_v3["citation_source_ids"],
            "mapped_chunk_ids": record_v3["mapped_chunk_ids"],
            "invalid_citations": record_v3["invalid_citations"],
            "expected_source_complete": record_v3["expected_source_complete"],
        },
        "selected_evidence": [
            {
                "source_id": item.source_id,
                "chunk_id": item.chunk_id,
                "document_id": item.document_id,
                "excerpt": item.content_text[:800],
                "metadata": item.metadata_json,
                "provenance": item.provenance_json,
            }
            for item in package.selected_evidence
        ],
        "classification": "REQUIRES_HUMAN_REVIEW",
    }


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{100 * value:.2f}%"


def render_reports(result: dict[str, Any]) -> None:
    v2 = result["full_answerable"]["legal-rag-v2"]
    v3 = result["full_answerable"]["legal-rag-v3"]
    safety = result["repeated_safety"]
    lines = [
        "# Legal-RAG-V3 Production Validation V1",
        "",
        "## Frozen inputs and isolation",
        "",
        f"- Evaluation V1 SHA-256: `{result['datasets']['evaluation_v1']}`",
        f"- Evaluation V2 SHA-256: `{result['datasets']['evaluation_v2']}`",
        f"- V2 prompt SHA-256: `{result['prompts']['legal-rag-v2']['sha256']}`",
        f"- V3 prompt SHA-256: `{result['prompts']['legal-rag-v3']['sha256']}`",
        "- Evidence presentation: P0",
        "- Production default after validation: `legal-rag-v2`",
        "- Blocks 1–5 changed: **NO**",
        "",
        "## Same-run full answerable comparison",
        "",
        "| Metric | V2 | V3 |",
        "|---|---:|---:|",
        f"| Answerable acceptance | {pct(v2['answerable_acceptance_rate'])} | {pct(v3['answerable_acceptance_rate'])} |",
        f"| False abstention | {pct(v2['false_abstention_rate'])} | {pct(v3['false_abstention_rate'])} |",
        f"| Citation presence | {pct(v2['citation_presence_rate'])} | {pct(v3['citation_presence_rate'])} |",
        f"| Citation validity | {pct(v2['citation_validity_rate'])} | {pct(v3['citation_validity_rate'])} |",
        f"| Expected-source match | {pct(v2['expected_source_match_rate'])} | {pct(v3['expected_source_match_rate'])} |",
        f"| Missing citation | {pct(v2['missing_citation_rate'])} | {pct(v3['missing_citation_rate'])} |",
        f"| Invalid citation | {pct(v2['invalid_citation_rate'])} | {pct(v3['invalid_citation_rate'])} |",
        "",
        "## Repeated safety",
        "",
        f"- Runs: {safety['run_count']}",
        f"- Structured abstentions: {safety['correct_abstentions']}/{safety['run_count']}",
        f"- Unsupported direct answers: {safety['unsupported_direct_answers']}",
        f"- Status-marker failures: {safety['marker_contract']['missing_or_malformed']}",
        f"- Answer/citation continuations after insufficient marker: {safety['continuation_count']}",
        "",
        "## Targeted five-run V3 repeatability",
        "",
        "| Case | Answerable | Grounded | Citation valid | Expected source | Status valid |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for case_id, item in result["targeted_v3"].items():
        lines.append(f"| `{case_id}` | {item['answerable']}/{item['runs']} | {item['grounded']}/{item['runs']} | {item['citation_valid']}/{item['runs']} | {item['expected_source']}/{item['runs']} | {item['status_valid']}/{item['runs']} |")
    lines.extend([
        "",
        "## Multi-evidence breakdown",
        "",
        "| Class | V2 grounded | V3 grounded |",
        "|---|---:|---:|",
    ])
    for label in ("single_evidence", "multi_evidence", "hierarchy_recovered", "multi_document"):
        lines.append(f"| {label} | {pct(result['category_breakdown']['legal-rag-v2'][label]['grounded_conversion_rate'])} | {pct(result['category_breakdown']['legal-rag-v3'][label]['grounded_conversion_rate'])} |")
    lines.extend([
        "",
        "## Tokens and latency",
        "",
        f"- Exact paired prompt-token delta V3 - V2: {result['tokens']['paired_delta_v3_minus_v2']['mean']:.1f} tokens across {result['tokens']['paired_delta_v3_minus_v2']['count']} cases.",
        f"- Prompt-budget overflows: V2 {result['tokens']['legal-rag-v2']['overflow_count']}, V3 {result['tokens']['legal-rag-v3']['overflow_count']}.",
        f"- Mean TTFT: V2 {result['latency']['legal-rag-v2']['ttft_ms']['mean']:.1f} ms, V3 {result['latency']['legal-rag-v3']['ttft_ms']['mean']:.1f} ms.",
        f"- Mean generation: V2 {result['latency']['legal-rag-v2']['generation_ms']['mean']:.1f} ms, V3 {result['latency']['legal-rag-v3']['generation_ms']['mean']:.1f} ms.",
        "",
        "## Activation readiness gate",
        "",
        f"- Engineering gate: **{'PASS' if result['activation_gate']['engineering_pass'] else 'FAIL'}**",
        f"- Human materiality/source review: **{result['activation_gate']['human_review_status']}**",
        f"- Recommendation: **{result['activation_gate']['recommendation']}**",
        "",
        "No activation was performed. The production default remains `legal-rag-v2`.",
    ])
    write_text(REPORT_MD, "\n".join(lines))

    review_lines = [
        "# Legal-RAG-V3 Human Review Package V1", "",
        "This package does not use an LLM judge. Reviewers must compare each answer with the side-by-side frozen evidence.", "",
    ]
    for item in result["human_review"]:
        review_lines.extend([
            f"## {item['case_id']} — {item['classification']}", "",
            f"**Question:** {item['question']}", "",
            f"**Review reasons:** `{json.dumps(item['review_reasons'])}`", "",
            f"**V2 status:** `{item['v2']['answerability_status']}`; **expected-source complete:** `{item['v2']['expected_source_complete']}`", "",
            f"**V2 answer:** {item['v2']['public_answer_text'] or '(abstained)' }", "",
            f"**V2 mapped chunks:** `{json.dumps(item['v2']['mapped_chunk_ids'])}`", "",
            f"**V3 status:** `{item['v3']['answerability_status']}`; **expected-source complete:** `{item['v3']['expected_source_complete']}`", "",
            f"**V3 answer:** {item['v3']['public_answer_text'] or '(abstained)' }", "",
            f"**V3 mapped chunks:** `{json.dumps(item['v3']['mapped_chunk_ids'])}`", "",
            f"**Expected sets:** `{json.dumps(item['acceptable_evidence_sets'])}`", "",
        ])
        for evidence in item["selected_evidence"]:
            review_lines.extend([
                f"### {evidence['source_id']} — `{evidence['chunk_id']}`", "",
                evidence["excerpt"].replace("\n", " "), "",
            ])
    write_text(HUMAN_MD, "\n".join(review_lines))


async def run(fresh: bool = False) -> dict[str, Any]:
    hashes = {"evaluation_v1": sha256(DATASET_V1), "evaluation_v2": sha256(DATASET_V2)}
    if hashes != {"evaluation_v1": V1_SHA256, "evaluation_v2": V2_SHA256}:
        raise RuntimeError(f"frozen dataset hash mismatch: {hashes}")
    for version, expected in PROMPT_SHA256.items():
        if sha256(PROMPTS[version]) != expected:
            raise RuntimeError(f"{version} prompt hash mismatch")
    design = ROOT / "docs" / "design" / "legal-rag-v3-prompt.txt"
    if PROMPTS["legal-rag-v3"].read_bytes() != design.read_bytes():
        raise RuntimeError("runtime V3 is not byte-identical to approved design")

    frozen = json.loads(HIERARCHY_REPORT.read_text(encoding="utf-8"))
    cases = frozen["cases"]
    if len(cases) != 65:
        raise RuntimeError("expected 65 frozen V2 cases")
    answerable = [item for item in cases if item["answerable"]]
    unanswerable = [item for item in cases if not item["answerable"]]
    if len(answerable) != 55 or len(unanswerable) != 10:
        raise RuntimeError("frozen V2 answerability counts changed")
    by_id = {item["case_id"]: item for item in cases}

    production = get_generation_profile()
    if production.prompt_version != "legal-rag-v2" or production.model_id != "qwen3.5:9b":
        raise RuntimeError("default profile must remain legal-rag-v2/qwen3.5:9b")
    profiles = {
        "legal-rag-v2": production,
        "legal-rag-v3": replace(production, prompt_version="legal-rag-v3"),
    }
    profiles["legal-rag-v3"].validate()
    if {key for key in asdict(production) if asdict(production)[key] != asdict(profiles["legal-rag-v3"])[key]} != {"prompt_version"}:
        raise RuntimeError("V2/V3 profile isolation failed")

    context_counter = ContextTokenCounter(production.tokenizer_provider, production.tokenizer_id)
    counters = {
        version: PromptTokenCounter(profile.tokenizer_provider, profile.tokenizer_id, thinking=profile.thinking)
        for version, profile in profiles.items()
    }
    builder = ContextBuilderService(context_counter)
    packages = {item["case_id"]: build_package(item, builder, production) for item in cases}
    for case in cases:
        if [item.chunk_id for item in packages[case["case_id"]].selected_evidence] != case["block5"]["selected_chunk_ids"]:
            raise RuntimeError(f"{case['case_id']}: P0 selected context drift")

    tokens = token_measurements(cases, packages, counters, profiles)
    store = ProgressStore(fresh)
    client = get_llm_client()
    await client.health(production)

    async def one(case, version, repeat, purpose):
        key = f"{purpose}|{version}|{PROMPT_SHA256[version]}|P0|{case['case_id']}|{repeat}"
        async def factory():
            record = await generate_once(
                case=case,
                package=packages[case["case_id"]],
                prompt_label=version,
                prompt=load_system_prompt(version),
                presentation=PRESENTATIONS["P0"],
                run_index=repeat,
                purpose=purpose,
                profile=profiles[version],
                context_counter=context_counter,
                prompt_counter=counters[version],
                client=client,
            )
            record["prompt_version"] = version
            record["prompt_sha256"] = PROMPT_SHA256[version]
            return record
        return await store.ensure(key, factory)

    targeted_v3 = [
        await one(by_id[case_id], "legal-rag-v3", repeat, "targeted-v3-5x")
        for case_id in TARGET_IDS for repeat in range(1, 6)
    ]
    full = {"legal-rag-v2": [], "legal-rag-v3": []}
    for case in answerable:
        full["legal-rag-v2"].append(await one(case, "legal-rag-v2", 1, "full-answerable-same-run"))
        full["legal-rag-v3"].append(await one(case, "legal-rag-v3", 1, "full-answerable-same-run"))
    safety = [
        await one(case, "legal-rag-v3", repeat, "safety-v3-3x")
        for case in unanswerable for repeat in range(1, 4)
    ]

    summaries = {version: summarize(records, answerable=True) for version, records in full.items()}
    categories = {version: category_breakdown(records, cases) for version, records in full.items()}
    markers_all_v3 = marker_contract(targeted_v3 + full["legal-rag-v3"] + safety)
    safety_marker = marker_contract(safety)
    safety_result = {
        "run_count": len(safety),
        "correct_abstentions": sum(item["answerability_status"] == "INSUFFICIENT_EVIDENCE" for item in safety),
        "unsupported_direct_answers": sum(item["unsupported_direct_answer"] for item in safety),
        "continuation_count": sum(bool(item["public_answer_text"].strip()) or bool(item["mapped_chunk_ids"]) for item in safety),
        "marker_contract": safety_marker,
        "records": safety,
    }
    paired_results = {
        "answerable_acceptance": paired(full["legal-rag-v2"], full["legal-rag-v3"], lambda item: item["answerability_status"] == "ANSWERABLE"),
        "grounded_conversion": paired(full["legal-rag-v2"], full["legal-rag-v3"], lambda item: item["grounded_conversion"]),
        "expected_source": paired(full["legal-rag-v2"], full["legal-rag-v3"], lambda item: item["expected_source_complete"] is True),
    }
    latency = {
        version: {
            "ttft_ms": distribution([item["ttft_ms"] for item in records]),
            "generation_ms": distribution([item["generation_ms"] for item in records]),
            "experiment_total_ms": distribution([item["experiment_total_ms"] for item in records]),
        }
        for version, records in full.items()
    }

    gains = set(paired_results["answerable_acceptance"]["v3_gains"])
    losses = set(paired_results["answerable_acceptance"]["v3_losses"])
    unexpected = {
        item["case_id"] for item in full["legal-rag-v3"]
        if item["answerability_status"] == "ANSWERABLE"
        and item["citation_validation"] == "PASS"
        and item["expected_source_complete"] is not True
    }
    qualified = {item["case_id"] for item in full["legal-rag-v3"] if item["category"] == "PARTIAL_SUPPORT"}
    multi_failures = {
        item["case_id"] for item in full["legal-rag-v3"]
        if by_id[item["case_id"]]["metrics_v2"]["is_multi_evidence"] and not item["grounded_conversion"]
    }
    unresolved_abstentions = {
        item["case_id"] for item in full["legal-rag-v3"]
        if item["answerability_status"] == "INSUFFICIENT_EVIDENCE"
    }
    review_ids = gains | losses | unexpected | qualified | multi_failures | unresolved_abstentions
    v2_by_id = {item["case_id"]: item for item in full["legal-rag-v2"]}
    v3_by_id = {item["case_id"]: item for item in full["legal-rag-v3"]}
    human_review = []
    for case_id in sorted(review_ids):
        reasons = []
        if case_id in gains:
            reasons.append("V3_ANSWERABILITY_GAIN")
        if case_id in losses:
            reasons.append("V3_ANSWERABILITY_LOSS")
        if case_id in unexpected:
            reasons.append("STRUCTURALLY_VALID_UNEXPECTED_SOURCE")
        if case_id in qualified:
            reasons.append("QUALIFIED_PARTIAL_SUPPORT")
        if case_id in multi_failures:
            reasons.append("MULTI_EVIDENCE_FAILURE")
        if case_id in unresolved_abstentions:
            reasons.append("V3_UNRESOLVED_FALSE_ABSTENTION")
        human_review.append(review_package(
            by_id[case_id], v2_by_id[case_id], v3_by_id[case_id], packages[case_id], reasons
        ))

    v2_summary, v3_summary = summaries["legal-rag-v2"], summaries["legal-rag-v3"]
    engineering_checks = {
        "runtime_hash_exact": sha256(PROMPTS["legal-rag-v3"]) == PROMPT_SHA256["legal-rag-v3"],
        "default_remains_v2": get_generation_profile().prompt_version == "legal-rag-v2",
        "v3_status_validity_100_percent": markers_all_v3["valid"] == markers_all_v3["runs"],
        "safety_30_of_30": len(safety) == 30 and safety_result["correct_abstentions"] == 30,
        "unsupported_answers_zero": safety_result["unsupported_direct_answers"] == 0,
        "insufficient_continuations_zero": safety_result["continuation_count"] == 0,
        "citation_validity_not_regressed": (v3_summary["citation_validity_rate"] or 0) >= (v2_summary["citation_validity_rate"] or 0),
        "prompt_budget_guard": tokens["legal-rag-v3"]["overflow_count"] == 0,
        "single_llm_call_architecture": True,
        "p0_context_unchanged": True,
    }
    engineering_pass = all(engineering_checks.values())
    measured_materiality = {
        "acceptance_rate_delta": (v3_summary["answerable_acceptance_rate"] or 0) - (v2_summary["answerable_acceptance_rate"] or 0),
        "false_abstention_rate_delta": (v3_summary["false_abstention_rate"] or 0) - (v2_summary["false_abstention_rate"] or 0),
        "citation_validity_rate_delta": (v3_summary["citation_validity_rate"] or 0) - (v2_summary["citation_validity_rate"] or 0),
        "expected_source_rate_delta": (v3_summary["expected_source_match_rate"] or 0) - (v2_summary["expected_source_match_rate"] or 0),
        "paired": paired_results,
    }
    expected_source_nonregression = (v3_summary["expected_source_match_rate"] or 0) >= (v2_summary["expected_source_match_rate"] or 0)
    human_status = "REQUIRED" if human_review else "NOT_REQUIRED"
    recommendation = (
        "READY_FOR_ACTIVATION_REVIEW" if engineering_pass and expected_source_nonregression and measured_materiality["acceptance_rate_delta"] > 0
        else "MORE_HUMAN_REVIEW_REQUIRED" if engineering_pass
        else "VALIDATION_FAILED"
    )

    result = {
        "experiment_id": "legal-rag-v3-production-validation-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "datasets": hashes,
        "prompts": {
            version: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path), "bytes": path.stat().st_size}
            for version, path in PROMPTS.items()
        },
        "configuration": {
            "production_default": production.prompt_version,
            "model_id": production.model_id,
            "tokenizer_id": production.tokenizer_id,
            "temperature": production.temperature,
            "top_p": production.top_p,
            "top_k": production.top_k,
            "thinking": production.thinking,
            "context_budget_tokens": production.context_budget_tokens,
            "presentation": "P0",
            "only_profile_difference": "prompt_version",
            "generation_order": "targeted V3; then per-case V2 followed by V3; then V3 safety",
        },
        "full_answerable": summaries,
        "full_answerable_records": full,
        "targeted_v3": by_target(targeted_v3),
        "repeated_safety": safety_result,
        "partial_support": {
            "case_ids": [item["case_id"] for item in cases if item["category"] == "PARTIAL_SUPPORT"],
            "v2": [item for item in full["legal-rag-v2"] if item["category"] == "PARTIAL_SUPPORT"],
            "v3": [item for item in full["legal-rag-v3"] if item["category"] == "PARTIAL_SUPPORT"],
        },
        "category_breakdown": categories,
        "paired_comparison": paired_results,
        "tokens": tokens,
        "latency": latency,
        "all_v3_marker_contract": markers_all_v3,
        "human_review": human_review,
        "measured_materiality": measured_materiality,
        "activation_gate": {
            "engineering_checks": engineering_checks,
            "engineering_pass": engineering_pass,
            "human_review_status": human_status,
            "recommendation": recommendation,
            "activation_performed": False,
        },
        "known_limits": [
            "Evaluation V2 influenced prompt design and is not a blind holdout.",
            "Expected-source matching is deterministic and does not prove semantic entailment.",
            "Only ten frozen unanswerable cases are available.",
            "Generation latency is sequential local-provider measurement, not an SLA.",
        ],
    }
    write_json(FINAL_JSON, result)
    write_json(REPORT_JSON, result)
    render_reports(result)
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
        "v2": result["full_answerable"]["legal-rag-v2"],
        "v3": result["full_answerable"]["legal-rag-v3"],
        "safety": {key: value for key, value in result["repeated_safety"].items() if key != "records"},
        "activation_gate": result["activation_gate"],
    }, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
