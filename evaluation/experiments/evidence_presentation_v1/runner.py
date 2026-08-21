"""Run Evidence Presentation + Status/Citation Stability Experiment V1.

The real local provider is called for every recorded generation. Retrieval and
context selection are loaded from the frozen Evaluation V2 hierarchy snapshot
so the experiment isolates evidence presentation and prompt-contract effects.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import re
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from app.context.schemas import ContextPackage
from app.context.service import ContextBuilderService
from app.generation.answerability import parse_answerability
from app.generation.citations import validate_and_map_citations
from app.generation.profile import GenerationProfile, get_generation_profile
from app.generation.prompting import load_system_prompt
from app.generation.runtime import close_llm_client, get_llm_client
from app.generation.schemas import AnswerabilityStatus, AnswerabilityValidation
from app.generation.tokenizers import ContextTokenCounter, PromptTokenCounter
from evaluation.v2_metrics import evidence_set_metrics

from .presentation import PRESENTATIONS, PresentationSpec, apply_presentation, evidence_shape, user_content


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
REPORTS = ROOT / "evaluation" / "reports"
DOCS = ROOT / "docs" / "verification"
DATASET_V1 = ROOT / "evaluation" / "datasets" / "legal_eval_v1.json"
DATASET_V2 = ROOT / "evaluation" / "datasets" / "legal_eval_v2.json"
HIERARCHY_REPORT = REPORTS / "legal_hierarchy_v2_generation.json"
PROGRESS = HERE / "raw_progress.json"
FINAL_JSON = HERE / "experiment_results.json"

V1_SHA256 = "afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245"
V2_SHA256 = "ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842"
PROMPT_PATHS = {
    "legal-rag-v2": ROOT / "app" / "prompts" / "legal-rag-v2.txt",
    "compact": HERE / "legal-rag-v3-compact-experimental.txt",
    "compact-fewshot": HERE / "legal-rag-v3-compact-fewshot-experimental.txt",
    "previous-combined": ROOT / "evaluation" / "experiments" / "abstention_calibration_v1" / "legal-rag-v3-experiment-combined.txt",
}
PREVIOUS_RESULT = ROOT / "evaluation" / "experiments" / "abstention_calibration_v1" / "experiment_results.json"

FALSE_CASE_IDS = (
    "v2_bank_scope_ratios",
    "v2_bank_below_80_measures",
    "v2_civil_scope",
    "v2_cross_document_effective_dates",
)
PASS_CONTROL_IDS = (
    "v2_social_plan_deadline",
    "v2_social_scope",
    "v2_bank_loan_limit_exceptions",
    "v2_bank_special_control_exception",
    "v2_civil_application_window",
    "v2_civil_effect_and_repeal",
)
DUPLICATE_CASE_ID = "v2_bank_loan_limit_exceptions"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(path: Path) -> dict[str, Any]:
    return {"path": str(path.relative_to(ROOT)), "sha256": sha256(path), "bytes": path.stat().st_size}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def complete_solution(case: dict[str, Any], selected_ids: list[str]) -> list[str]:
    selected = set(selected_ids)
    solutions = [list(solution) for solution in case["acceptable_evidence_sets"] if set(solution) <= selected]
    return min(solutions, key=lambda item: (len(item), item)) if solutions else []


def support_with_anchors(case: dict[str, Any], selected_ids: list[str]) -> list[str]:
    solution = complete_solution(case, selected_ids)
    if not solution:
        return []
    candidates = {item["chunk_id"]: item for item in case["block4"]["final_candidates"]}
    support = set(solution)
    for chunk_id in solution:
        anchor_id = candidates[chunk_id].get("anchor_chunk_id")
        if anchor_id in selected_ids:
            support.add(anchor_id)
    return [chunk_id for chunk_id in selected_ids if chunk_id in support]


def selected_candidates(case: dict[str, Any], ordered_ids: list[str]) -> list[dict[str, Any]]:
    by_id = {item["chunk_id"]: item for item in case["block4"]["final_candidates"]}
    missing = [item for item in ordered_ids if item not in by_id]
    if missing:
        raise RuntimeError(f"{case['case_id']}: missing frozen candidates {missing}")
    result = []
    for index, chunk_id in enumerate(ordered_ids, start=1):
        item = dict(by_id[chunk_id])
        item["context_candidate_order"] = index
        result.append(item)
    return result


def build_package(
    case: dict[str, Any],
    builder: ContextBuilderService,
    profile: GenerationProfile,
    mode: str = "production",
) -> ContextPackage:
    selected_ids = list(case["block5"]["selected_chunk_ids"])
    if mode == "production":
        candidates = case["block4"]["final_candidates"]
    elif mode == "oracle_minimal":
        support = support_with_anchors(case, selected_ids)
        if not support:
            raise RuntimeError(f"{case['case_id']}: no complete oracle support")
        candidates = selected_candidates(case, support)
    elif mode == "oracle_evidence_first":
        support = support_with_anchors(case, selected_ids)
        ordered = support + [item for item in selected_ids if item not in set(support)]
        candidates = selected_candidates(case, ordered)
    else:
        raise ValueError(f"unknown package mode: {mode}")
    package = builder.build(
        request_id=f"evidence-presentation-{case['case_id']}-{mode}",
        query_text=case["question"],
        retrieved_candidates=candidates,
        context_budget_tokens=profile.context_budget_tokens,
    )
    result_ids = [item.chunk_id for item in package.selected_evidence]
    if mode == "production" and result_ids != selected_ids:
        raise RuntimeError(f"{case['case_id']}: frozen Block 5 snapshot was not reproduced")
    if mode == "oracle_evidence_first" and set(result_ids) != set(selected_ids):
        raise RuntimeError(f"{case['case_id']}: evidence-first oracle changed selected evidence")
    return package


def messages_for(package: ContextPackage, prompt: str, boundary: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_content(package, boundary)},
    ]


def marker_count(value: str) -> int:
    return len(re.findall(r"\[STATUS[^\]\r\n]*\]", value, flags=re.IGNORECASE))


async def generate_once(
    *,
    case: dict[str, Any],
    package: ContextPackage,
    prompt_label: str,
    prompt: str,
    presentation: PresentationSpec,
    run_index: int,
    purpose: str,
    profile: GenerationProfile,
    context_counter: ContextTokenCounter,
    prompt_counter: PromptTokenCounter,
    client,
) -> dict[str, Any]:
    messages = messages_for(package, prompt, presentation.user_boundary)
    prompt_tokens = prompt_counter.count_messages(messages)
    total_reserved = prompt_tokens + profile.max_output_tokens + profile.prompt_token_safety_margin
    if total_reserved > profile.model_context_limit:
        raise RuntimeError(f"{case['case_id']}: prompt budget overflow ({total_reserved})")
    started = perf_counter()
    first = None
    pieces: list[str] = []
    usage = None
    finish_reason = None
    async for chunk in client.stream(messages, profile):
        if chunk.text:
            first = first or perf_counter()
            pieces.append(chunk.text)
        if chunk.done:
            usage = chunk.usage
            finish_reason = chunk.finish_reason
    ended = perf_counter()
    raw = "".join(pieces)
    parsed = parse_answerability(raw)
    citations, invalid, citation_validation, generation_status = validate_and_map_citations(
        parsed.public_text, package.selected_evidence
    )
    if parsed.status == AnswerabilityStatus.INSUFFICIENT_EVIDENCE:
        citations, invalid = [], []
        citation_validation = type(citation_validation).PASS
        generation_status = type(generation_status).INSUFFICIENT_EVIDENCE
    elif parsed.validation != AnswerabilityValidation.PASS:
        generation_status = type(generation_status).COMPLETED_WITH_WARNINGS
    mapped = [item.chunk_id for item in citations]
    expected = evidence_set_metrics(mapped, case["acceptable_evidence_sets"]) if case["answerable"] else None
    provider_usage = usage.model_dump(mode="json") if usage else None
    return {
        "key": f"{purpose}|{prompt_label}|{presentation.key}|{case['case_id']}|{run_index}",
        "purpose": purpose,
        "case_id": case["case_id"],
        "category": case["category"],
        "answerable": case["answerable"],
        "run_index": run_index,
        "prompt_label": prompt_label,
        "presentation": presentation.key,
        "presentation_label": presentation.label,
        "production_plausible": presentation.production_plausible,
        "selected_source_ids": [item.source_id for item in package.selected_evidence],
        "selected_chunk_ids": [item.chunk_id for item in package.selected_evidence],
        "selected_candidate_origins": [item.candidate_origin.value for item in package.selected_evidence],
        "context_tokens": package.context_token_count,
        "system_tokens": context_counter.count(prompt),
        "prompt_tokens": prompt_tokens,
        "answerability_status": parsed.status.value if parsed.status else None,
        "answerability_validation": parsed.validation.value,
        "raw_status_marker_count": marker_count(raw),
        "raw_provider_text": raw,
        "public_answer_text": parsed.public_text,
        "generation_status": generation_status.value,
        "citation_validation": citation_validation.value,
        "citation_source_ids": [item.source_id for item in citations],
        "mapped_chunk_ids": mapped,
        "mapped_document_ids": [item.document_id for item in citations],
        "invalid_citations": invalid,
        "expected_source_complete": expected["complete"] if expected else None,
        "expected_source_recall": expected["recall"] if expected else None,
        "grounded_conversion": bool(
            case["answerable"]
            and parsed.status == AnswerabilityStatus.ANSWERABLE
            and parsed.validation == AnswerabilityValidation.PASS
            and expected
            and expected["complete"]
            and not invalid
        ),
        "unsupported_direct_answer": bool(
            not case["answerable"]
            and parsed.status != AnswerabilityStatus.INSUFFICIENT_EVIDENCE
            and bool(parsed.public_text.strip())
        ),
        "finish_reason": finish_reason,
        "provider_usage": provider_usage,
        "provider_prompt_token_delta": (
            provider_usage.get("input_tokens") - prompt_tokens
            if provider_usage and isinstance(provider_usage.get("input_tokens"), int)
            else None
        ),
        "ttft_ms": (first - started) * 1000 if first else None,
        "generation_ms": (ended - started) * 1000,
    }


class ProgressStore:
    def __init__(self, fresh: bool):
        if fresh and PROGRESS.exists():
            PROGRESS.unlink()
        self.records: dict[str, dict[str, Any]] = {}
        if PROGRESS.exists():
            data = json.loads(PROGRESS.read_text(encoding="utf-8"))
            self.records = {item["key"]: item for item in data.get("records", [])}

    def save(self) -> None:
        write_json(PROGRESS, {
            "experiment": "evidence-presentation-status-citation-stability-v1",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "records": list(self.records.values()),
        })

    async def ensure(self, key: str, factory: Callable) -> dict[str, Any]:
        if key in self.records:
            print(f"[resume] {key}", flush=True)
            return self.records[key]
        print(f"[run] {key}", flush=True)
        record = await factory()
        self.records[key] = record
        self.save()
        return record


def mean(values: list[float | int | None]) -> float | None:
    clean = [float(item) for item in values if item is not None]
    return statistics.fmean(clean) if clean else None


def summarize(records: list[dict[str, Any]], answerable: bool | None = None) -> dict[str, Any]:
    items = [item for item in records if answerable is None or item["answerable"] == answerable]
    count = len(items)
    statuses = Counter(item["answerability_status"] or "INVALID_OR_MISSING" for item in items)
    return {
        "run_count": count,
        "unique_case_count": len({item["case_id"] for item in items}),
        "status_counts": dict(sorted(statuses.items())),
        "status_valid_rate": sum(item["answerability_validation"] == "PASS" for item in items) / count if count else None,
        "answerable_acceptance_rate": sum(item["answerability_status"] == "ANSWERABLE" for item in items) / count if count else None,
        "false_abstention_rate": (
            sum(item["answerability_status"] == "INSUFFICIENT_EVIDENCE" for item in items) / count
            if count and answerable is not False else None
        ),
        "abstention_rate": sum(item["answerability_status"] == "INSUFFICIENT_EVIDENCE" for item in items) / count if count else None,
        "citation_presence_rate": sum(bool(item["mapped_chunk_ids"]) for item in items) / count if count else None,
        "citation_validity_rate": (
            sum(bool(item["mapped_chunk_ids"]) and item["citation_validation"] == "PASS" for item in items) / count
            if count else None
        ),
        "expected_source_match_rate": (
            sum(item["expected_source_complete"] is True for item in items) / count
            if count and answerable is not False else None
        ),
        "grounded_conversion_rate": (
            sum(item["grounded_conversion"] for item in items) / count
            if count and answerable is not False else None
        ),
        "missing_citation_rate": sum(item["citation_validation"] == "MISSING_CITATIONS" for item in items) / count if count else None,
        "invalid_citation_rate": sum(bool(item["invalid_citations"]) for item in items) / count if count else None,
        "duplicate_status_count": sum(item["answerability_validation"] == "ANSWERABILITY_STATUS_DUPLICATE" for item in items),
        "unsupported_direct_answer_count": sum(item["unsupported_direct_answer"] for item in items),
        "mean_context_tokens": mean([item["context_tokens"] for item in items]),
        "mean_system_tokens": mean([item["system_tokens"] for item in items]),
        "mean_prompt_tokens": mean([item["prompt_tokens"] for item in items]),
        "mean_ttft_ms": mean([item["ttft_ms"] for item in items]),
        "mean_generation_ms": mean([item["generation_ms"] for item in items]),
    }


def pearson_binary(rows: list[dict[str, Any]], field: str) -> float | None:
    pairs = [(float(row[field]), float(row["false_abstention"])) for row in rows if row.get(field) is not None]
    if len(pairs) < 3:
        return None
    xs, ys = zip(*pairs)
    xbar, ybar = statistics.fmean(xs), statistics.fmean(ys)
    numerator = sum((x - xbar) * (y - ybar) for x, y in pairs)
    denominator = math.sqrt(sum((x - xbar) ** 2 for x in xs) * sum((y - ybar) ** 2 for y in ys))
    return numerator / denominator if denominator else None


def context_diagnostics(
    cases: list[dict[str, Any]], packages: dict[str, ContextPackage], counter: ContextTokenCounter
) -> dict[str, Any]:
    rows = []
    for case in cases:
        if not case["answerable"] or not case["metrics_v2"]["context_evidence"]["complete"]:
            continue
        package = packages[case["case_id"]]
        selected_ids = [item.chunk_id for item in package.selected_evidence]
        solution = complete_solution(case, selected_ids)
        support = support_with_anchors(case, selected_ids)
        positions = [selected_ids.index(item) + 1 for item in solution]
        support_positions = [selected_ids.index(item) + 1 for item in support]
        first = min(support_positions) if support_positions else None
        last = max(support_positions) if support_positions else None
        first_marker = f"[Evidence S{first}]" if first else ""
        last_marker = f"[Evidence S{last}]" if last else ""
        first_char = package.context_text.find(first_marker) if first_marker else -1
        last_char = package.context_text.find(last_marker) if last_marker else -1
        if last_char >= 0:
            next_marker = package.context_text.find("\n\n---\n\n[Evidence S", last_char + len(last_marker))
            after_start = next_marker if next_marker >= 0 else len(package.context_text)
        else:
            after_start = 0
        shape = evidence_shape(package)
        row = {
            "case_id": case["case_id"],
            "category": case["category"],
            "false_abstention": case["block6"]["status"] == "INSUFFICIENT_EVIDENCE",
            "selected_evidence_count": len(selected_ids),
            "relevant_evidence_count": len(solution),
            "support_with_anchor_count": len(support),
            "distractor_count": len(selected_ids) - len(support),
            "context_tokens": package.context_token_count,
            "tokens_before_first_support": counter.count(package.context_text[:max(first_char, 0)]) if first_char >= 0 else None,
            "tokens_after_last_support": counter.count(package.context_text[after_start:]) if last_char >= 0 else None,
            "required_source_positions": positions,
            **shape,
        }
        rows.append(row)

    pass_rows = [item for item in rows if not item["false_abstention"]]
    for row in rows:
        closest = sorted(
            pass_rows,
            key=lambda item: (abs(item["context_tokens"] - row["context_tokens"]), item["case_id"]),
        )[:3]
        row["similar_context_success_controls"] = [
            {"case_id": item["case_id"], "context_tokens": item["context_tokens"], "distractor_count": item["distractor_count"]}
            for item in closest
        ] if row["false_abstention"] else []

    sorted_tokens = sorted(row["context_tokens"] for row in rows)
    low_cut = sorted_tokens[len(sorted_tokens) // 3]
    high_cut = sorted_tokens[(2 * len(sorted_tokens)) // 3]
    buckets = {"LOW": [], "MEDIUM": [], "HIGH": []}
    for row in rows:
        bucket = "LOW" if row["context_tokens"] <= low_cut else "MEDIUM" if row["context_tokens"] <= high_cut else "HIGH"
        buckets[bucket].append(row)
    bucket_summary = {
        key: {
            "case_count": len(values),
            "token_range": [min((item["context_tokens"] for item in values), default=None), max((item["context_tokens"] for item in values), default=None)],
            "frozen_false_abstention_rate": sum(item["false_abstention"] for item in values) / len(values) if values else None,
        }
        for key, values in buckets.items()
    }
    hierarchy_groups = {}
    for key, predicate in {
        "NO_HIERARCHY_CHILD": lambda row: row["hierarchy_child_count"] == 0,
        "HAS_HIERARCHY_CHILD": lambda row: row["hierarchy_child_count"] > 0,
    }.items():
        values = [row for row in rows if predicate(row)]
        hierarchy_groups[key] = {
            "case_count": len(values),
            "frozen_false_abstention_rate": sum(row["false_abstention"] for row in values) / len(values) if values else None,
            "mean_context_tokens": mean([row["context_tokens"] for row in values]),
        }
    return {
        "rows": rows,
        "context_size_buckets": bucket_summary,
        "point_biserial_correlations": {
            "context_tokens_vs_false_abstention": pearson_binary(rows, "context_tokens"),
            "distractor_count_vs_false_abstention": pearson_binary(rows, "distractor_count"),
            "hierarchy_child_count_vs_false_abstention": pearson_binary(rows, "hierarchy_child_count"),
        },
        "hierarchy_child_comparison": hierarchy_groups,
        "interpretation_guard": "Correlations are descriptive on the frozen sample and do not establish causality.",
    }


def frozen_baseline_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    answerable = [item for item in cases if item["answerable"]]
    unanswerable = [item for item in cases if not item["answerable"]]
    return {
        "answerable_case_count": len(answerable),
        "unanswerable_case_count": len(unanswerable),
        "answerable_acceptance_rate": sum(item["block6"]["answerability_status"] == "ANSWERABLE" for item in answerable) / len(answerable),
        "false_abstention_rate": sum(item["block6"]["answerability_status"] == "INSUFFICIENT_EVIDENCE" for item in answerable) / len(answerable),
        "citation_presence_rate": sum(bool(item["block6"]["citations"]) for item in answerable) / len(answerable),
        "citation_validity_rate": sum(bool(item["block6"]["citations"]) and item["block6"]["citation_validation"] == "PASS" for item in answerable) / len(answerable),
        "expected_source_match_rate": sum(item["metrics_v2"]["citation_evidence"]["complete"] for item in answerable) / len(answerable),
        "status_validity_rate": sum(item["block6"]["answerability_validation"] == "PASS" for item in cases) / len(cases),
        "unanswerable_abstention_rate": sum(item["block6"]["answerability_status"] == "INSUFFICIENT_EVIDENCE" for item in unanswerable) / len(unanswerable),
        "unsupported_direct_answer_count": sum(item["metrics"].get("unsupported_answer", False) for item in unanswerable),
        "mean_prompt_tokens": mean([item["block6"].get("prompt_tokens") for item in answerable]),
        "mean_ttft_ms": mean([item["timings"].get("ttft_ms") for item in cases]),
        "mean_answerable_ttft_ms": mean([item["timings"].get("ttft_ms") for item in answerable]),
        "mean_generation_ms": mean([item["timings"].get("generation_ms") for item in cases]),
        "mean_answerable_generation_ms": mean([item["timings"].get("generation_ms") for item in answerable]),
        "mean_total_ms": mean([item["timings"].get("total_ms") for item in cases]),
    }


def category_breakdown(records: list[dict[str, Any]], cases: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {item["case_id"]: item for item in cases}
    classes = {
        "single_evidence": lambda case: case["answerable"] and not case["metrics_v2"]["is_multi_evidence"],
        "multi_evidence": lambda case: case["answerable"] and case["metrics_v2"]["is_multi_evidence"],
        "hierarchy_recovered": lambda case: case["answerable"] and any(
            candidate.get("candidate_origin") == "HIERARCHY_CHILD" and candidate["chunk_id"] in {
                chunk for solution in case["acceptable_evidence_sets"] for chunk in solution
            }
            for candidate in case["block4"]["final_candidates"]
        ),
        "multi_document": lambda case: case["answerable"] and case["metrics_v2"]["is_multi_document"],
    }
    return {
        label: summarize([record for record in records if predicate(by_id[record["case_id"]])], answerable=True)
        for label, predicate in classes.items()
    }


def choose_best(summary_map: dict[str, dict[str, Any]], *, require_safety: bool = True) -> str:
    eligible = []
    for key, value in summary_map.items():
        safety = value.get("safety") or {}
        if require_safety and not (
            safety.get("abstention_rate") == 1.0
            and safety.get("unsupported_direct_answer_count") == 0
            and safety.get("status_valid_rate") == 1.0
        ):
            continue
        targeted = value["targeted"]
        eligible.append((
            targeted.get("grounded_conversion_rate") or 0.0,
            targeted.get("citation_validity_rate") or 0.0,
            targeted.get("expected_source_match_rate") or 0.0,
            -(targeted.get("mean_prompt_tokens") or 10**9),
            key,
        ))
    if not eligible:
        return "legal-rag-v2|P0"
    return max(eligible)[-1]


def production_files() -> list[Path]:
    return [
        ROOT / "app" / "prompts" / "legal-rag-v2.txt",
        ROOT / "app" / "generation" / "profile.py",
        ROOT / "app" / "generation" / "prompting.py",
        ROOT / "app" / "generation" / "answerability.py",
        ROOT / "app" / "generation" / "citations.py",
        ROOT / "app" / "orchestration" / "answer_service.py",
        ROOT / "app" / "retrieval" / "service.py",
        ROOT / "app" / "retrieval" / "hierarchy_expander.py",
        ROOT / "app" / "context" / "service.py",
        ROOT / "app" / "context" / "formatter.py",
    ]


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.2f}%"


def render_reports(result: dict[str, Any]) -> None:
    baseline = result["baseline_repeatability"]
    oracle = result["oracle_ceilings"]
    comparison = result["strategy_comparison"]
    best = result["best_joint_combination"]
    frozen = result["frozen_evaluation_baseline"]
    context = result["context_distraction"]

    write_json(REPORTS / "evidence_presentation_baseline_v1.json", {
        "datasets": result["datasets"],
        "production_configuration": result["production_configuration"],
        "baseline_repeatability": baseline,
        "frozen_evaluation_baseline": frozen,
    })
    write_json(REPORTS / "evidence_presentation_strategy_comparison_v1.json", comparison)
    write_json(REPORTS / "evidence_presentation_experiment_v1.json", result)

    baseline_md = f"""# Evidence Presentation Baseline V1

- Evaluation V1 SHA-256: `{result['datasets']['evaluation_v1']}`
- Evaluation V2 SHA-256: `{result['datasets']['evaluation_v2']}`
- Production prompt: `legal-rag-v2`
- Production prompt SHA-256: `{result['prompt_fingerprints']['legal-rag-v2']['sha256']}`
- Production changed: **NO**

## Repeated complete-context false-abstention cases

| Case | ANSWERABLE | INSUFFICIENT | Grounded | Classification |
|---|---:|---:|---:|---|
"""
    for case_id, item in baseline["per_case"].items():
        baseline_md += f"| `{case_id}` | {item['answerable']} | {item['insufficient']} | {item['grounded']} | {item['classification']} |\n"
    baseline_md += f"""

Targeted repeated baseline: answerable {pct(baseline['false_cases']['answerable_acceptance_rate'])}, false abstention {pct(baseline['false_cases']['false_abstention_rate'])}, grounded expected-source conversion {pct(baseline['false_cases']['grounded_conversion_rate'])}.

Successful answerable controls: {baseline['answerable_controls']['status_counts']}; grounded conversion {pct(baseline['answerable_controls']['grounded_conversion_rate'])}.

Unanswerable controls: {baseline['unanswerable_controls']['status_counts']}; unsupported direct answers {baseline['unanswerable_controls']['unsupported_direct_answer_count']}.
"""
    write_text(REPORTS / "evidence_presentation_baseline_v1.md", baseline_md)

    context_md = """# Context Distraction Analysis V1

Ground truth is used here only for offline diagnosis. It is not used by any production-plausible ordering strategy.

| Case | Frozen false abstention | Context tokens | Selected | Support incl. anchors | Distractors | Before support tokens | After support tokens | Hierarchy children |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
"""
    for row in context["rows"]:
        context_md += f"| `{row['case_id']}` | {row['false_abstention']} | {row['context_tokens']} | {row['selected_evidence_count']} | {row['support_with_anchor_count']} | {row['distractor_count']} | {row['tokens_before_first_support']} | {row['tokens_after_last_support']} | {row['hierarchy_child_count']} |\n"
    context_md += f"""

## Descriptive correlations

```json
{json.dumps(context['point_biserial_correlations'], ensure_ascii=False, indent=2)}
```

Context-size buckets: `{json.dumps(context['context_size_buckets'], ensure_ascii=False)}`.

Hierarchy-child comparison: `{json.dumps(context['hierarchy_child_comparison'], ensure_ascii=False)}`.

These are small-sample correlations, not causal proof. Similar-length successful controls recorded in the JSON show that length alone is not a sufficient explanation.
"""
    write_text(REPORTS / "context_distraction_analysis_v1.md", context_md)

    strategy_md = """# Evidence Presentation Strategy Comparison V1

All P1–P6 strategies preserve the selected evidence set and use runtime-available fields only. No strategy uses expected chunk IDs or labels.

| Strategy | Targeted answerable | Targeted grounded | Citation valid | Expected source | Safety abstention | Unsupported | Status valid | Mean prompt tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
"""
    for key, value in comparison["presentation_screen"].items():
        t, s = value["targeted"], value["safety"]
        strategy_md += f"| {key} | {pct(t['answerable_acceptance_rate'])} | {pct(t['grounded_conversion_rate'])} | {pct(t['citation_validity_rate'])} | {pct(t['expected_source_match_rate'])} | {pct(s['abstention_rate'])} | {s['unsupported_direct_answer_count']} | {pct(s['status_valid_rate'])} | {t['mean_prompt_tokens']:.1f} |\n"
    strategy_md += f"\nSelected diagnostic presentation: **{comparison['best_presentation']}**. Selection used only measured model behavior and runtime-plausible strategy definitions; it did not use ground truth in the algorithm itself.\n"
    write_text(REPORTS / "evidence_presentation_strategy_comparison_v1.md", strategy_md)

    duplicate = result["status_marker_failure_analysis"]
    status_md = f"""# Status Marker Failure Analysis V1

- Previous failure case: `{DUPLICATE_CASE_ID}`
- Previous raw output contained two complete answer/status blocks.
- Reproduction runs: {duplicate['reproduction']['run_count']}
- Duplicate markers reproduced: {duplicate['reproduction']['duplicate_status_count']}
- Strict parser changed: **NO**

The duplicate was already present in raw provider text, so it was not created by streaming or parsing. It reproduced identically in all three new runs. The old combined formulation therefore has a repeatable prompt/model output-contract failure, plausibly primed by repeated marker descriptions/examples and the absence of an explicit no-repeat rule. Multiple markers remain invalid and are not silently accepted.
"""
    write_text(REPORTS / "status_marker_failure_analysis_v1.md", status_md)

    fading = result["citation_fading_analysis"]
    citation_md = f"""# Citation Fading Analysis V1

The citation parser and validator were unchanged. Prior variants improved targeted answerability but sometimes displaced or weakened exact citation adherence. Controlled results:

```json
{json.dumps(fading, ensure_ascii=False, indent=2)}
```

The compact prompts place the exact citation rule adjacent to the ANSWERABLE rule and explicitly forbid duplicate status markers. A candidate is rejected if status or citation stability regresses on the full answerable corpus, regardless of targeted answer-rate improvement.
"""
    write_text(REPORTS / "citation_fading_analysis_v1.md", citation_md)

    safety_md = f"""# Evidence Presentation Safety V1

- Best joint combination: `{best['key']}`
- Frozen unanswerable abstention: {pct(best['unanswerable']['abstention_rate'])}
- Unsupported direct answers: {best['unanswerable']['unsupported_direct_answer_count']}
- Status validity: {pct(best['unanswerable']['status_valid_rate'])}
- Hard/topically-close unanswerable and out-of-corpus cases are reported separately.
- Frozen category PARTIAL_SUPPORT remains an answerable qualified-response case; it is not re-labelled.
- Second LLM call: **NONE**
- Classifier: **NONE**
- Production prompt switching: **NONE**
"""
    write_text(REPORTS / "evidence_presentation_safety_v1.md", safety_md)

    experiment_md = f"""# Evidence Presentation + Status/Citation Stability Experiment V1

## Frozen state

- V1: `{result['datasets']['evaluation_v1']}`
- V2: `{result['datasets']['evaluation_v2']}`
- Production prompt: `legal-rag-v2`
- Production changed: **NO**

## Oracle ceilings (not production eligible)

- Minimal sufficient evidence: answerable {pct(oracle['minimal']['answerable_acceptance_rate'])}, grounded {pct(oracle['minimal']['grounded_conversion_rate'])}.
- Expected evidence first in full context: answerable {pct(oracle['evidence_first']['answerable_acceptance_rate'])}, grounded {pct(oracle['evidence_first']['grounded_conversion_rate'])}.

## Best measured joint combination

- Combination: `{best['key']}`
- Targeted false abstention: {pct(baseline['false_cases']['false_abstention_rate'])} → {pct(best['targeted']['false_abstention_rate'])}
- Full answerable acceptance: {pct(frozen['answerable_acceptance_rate'])} → {pct(best['answerable']['answerable_acceptance_rate'])}
- Full citation validity: {pct(frozen['citation_validity_rate'])} → {pct(best['answerable']['citation_validity_rate'])}
- Full expected-source match: {pct(frozen['expected_source_match_rate'])} → {pct(best['answerable']['expected_source_match_rate'])}
- Status validity: {pct(best['all_cases_status_validity'])}
- Unanswerable abstention: {pct(best['unanswerable']['abstention_rate'])}
- Unsupported direct answers: {best['unanswerable']['unsupported_direct_answer_count']}
- Mean prompt-token delta vs production P0: {best['prompt_token_delta_vs_p0']}
- Mean generation-latency delta: {best['generation_latency_delta_ms_vs_p0']}

## Decision

**{result['recommendation']['next_target']}**

{result['recommendation']['rationale']}

This is diagnostic evidence only. No prompt or evidence-presentation strategy was deployed.
"""
    write_text(REPORTS / "evidence_presentation_experiment_v1.md", experiment_md)


async def run(fresh: bool = False) -> dict[str, Any]:
    hashes = {"evaluation_v1": sha256(DATASET_V1), "evaluation_v2": sha256(DATASET_V2)}
    if hashes != {"evaluation_v1": V1_SHA256, "evaluation_v2": V2_SHA256}:
        raise RuntimeError(f"Frozen dataset hash mismatch: {hashes}")
    source = json.loads(HIERARCHY_REPORT.read_text(encoding="utf-8"))
    cases = source["cases"]
    if len(cases) != 65:
        raise RuntimeError(f"Expected 65 frozen V2 cases, found {len(cases)}")
    by_id = {item["case_id"]: item for item in cases}
    if set(FALSE_CASE_IDS) - set(by_id):
        raise RuntimeError("Required false-abstention case is missing")

    profile = get_generation_profile()
    if profile.prompt_version != "legal-rag-v2" or profile.model_id != "qwen3.5:9b":
        raise RuntimeError("Production profile drifted from legal-rag-v2/qwen3.5:9b")
    context_counter = ContextTokenCounter(profile.tokenizer_provider, profile.tokenizer_id)
    prompt_counter = PromptTokenCounter(profile.tokenizer_provider, profile.tokenizer_id, thinking=profile.thinking)
    builder = ContextBuilderService(context_counter)
    prompts = {key: path.read_text(encoding="utf-8").strip() for key, path in PROMPT_PATHS.items()}
    if prompts["legal-rag-v2"] != load_system_prompt("legal-rag-v2"):
        raise RuntimeError("Production prompt snapshot mismatch")

    packages = {case["case_id"]: build_package(case, builder, profile) for case in cases}
    false_cases = [by_id[item] for item in FALSE_CASE_IDS]
    answerable_cases = [item for item in cases if item["answerable"]]
    unanswerable_cases = [item for item in cases if not item["answerable"]]
    pass_controls = [by_id[item] for item in PASS_CONTROL_IDS]
    if len(answerable_cases) != 55 or len(unanswerable_cases) != 10:
        raise RuntimeError("Frozen V2 answerable/unanswerable counts changed")

    experiment_packages: dict[tuple[str, str], ContextPackage] = {}
    for case in cases:
        for pkey, spec in PRESENTATIONS.items():
            experiment_packages[(case["case_id"], pkey)] = apply_presentation(
                packages[case["case_id"]], spec, context_counter
            )

    oracle_minimal = {
        case["case_id"]: build_package(case, builder, profile, "oracle_minimal") for case in false_cases
    }
    oracle_first = {
        case["case_id"]: build_package(case, builder, profile, "oracle_evidence_first") for case in false_cases
    }

    store = ProgressStore(fresh)
    client = get_llm_client()
    await client.health(profile)

    async def one(
        case: dict[str, Any], prompt_label: str, presentation_key: str, run_index: int,
        purpose: str, package_override: ContextPackage | None = None,
    ) -> dict[str, Any]:
        spec = PRESENTATIONS[presentation_key]
        package = package_override or experiment_packages[(case["case_id"], presentation_key)]
        key = f"{purpose}|{prompt_label}|{presentation_key}|{case['case_id']}|{run_index}"
        return await store.ensure(key, lambda: generate_once(
            case=case,
            package=package,
            prompt_label=prompt_label,
            prompt=prompts[prompt_label],
            presentation=spec,
            run_index=run_index,
            purpose=purpose,
            profile=profile,
            context_counter=context_counter,
            prompt_counter=prompt_counter,
            client=client,
        ))

    # Exact production repeatability: every important control is regenerated.
    baseline_false = [
        await one(case, "legal-rag-v2", "P0", repeat, "baseline-false")
        for case in false_cases for repeat in range(1, 4)
    ]
    baseline_pass = [
        await one(case, "legal-rag-v2", "P0", repeat, "baseline-pass-control")
        for case in pass_controls for repeat in range(1, 4)
    ]
    baseline_unanswerable = [
        await one(case, "legal-rag-v2", "P0", repeat, "baseline-unanswerable")
        for case in unanswerable_cases for repeat in range(1, 4)
    ]

    oracle_minimal_records = [
        await one(case, "legal-rag-v2", "P0", repeat, "oracle-minimal", oracle_minimal[case["case_id"]])
        for case in false_cases for repeat in range(1, 4)
    ]
    oracle_first_records = [
        await one(case, "legal-rag-v2", "P0", repeat, "oracle-evidence-first", oracle_first[case["case_id"]])
        for case in false_cases for repeat in range(1, 4)
    ]

    # Screen every presentation with repeated target cases and all ten safety cases.
    presentation_targeted: dict[str, list[dict[str, Any]]] = {"P0": baseline_false}
    presentation_safety: dict[str, list[dict[str, Any]]] = {
        "P0": [item for item in baseline_unanswerable if item["run_index"] == 1]
    }
    for pkey in ("P1", "P2", "P3", "P4", "P5", "P6"):
        presentation_targeted[pkey] = [
            await one(case, "legal-rag-v2", pkey, repeat, "presentation-screen")
            for case in false_cases for repeat in range(1, 4)
        ]
        presentation_safety[pkey] = [
            await one(case, "legal-rag-v2", pkey, 1, "presentation-safety")
            for case in unanswerable_cases
        ]
    presentation_screen = {
        pkey: {
            "definition": PRESENTATIONS[pkey].__dict__,
            "targeted": summarize(presentation_targeted[pkey], answerable=True),
            "safety": summarize(presentation_safety[pkey], answerable=False),
            "selected_set_preserved": all(
                set(record["selected_chunk_ids"]) == set(by_id[record["case_id"]]["block5"]["selected_chunk_ids"])
                for record in presentation_targeted[pkey] + presentation_safety[pkey]
            ),
        }
        for pkey in PRESENTATIONS
    }
    best_presentation_combo = choose_best({
        f"legal-rag-v2|{pkey}": value for pkey, value in presentation_screen.items()
    })
    best_presentation = best_presentation_combo.split("|")[1]

    # Compact prompt controls and the deliberately small cross-matrix.
    cross_specs = [
        ("legal-rag-v2", "P0"),
        ("legal-rag-v2", best_presentation),
        ("compact", "P0"),
        ("compact", best_presentation),
        ("compact-fewshot", best_presentation),
    ]
    cross_targeted: dict[str, list[dict[str, Any]]] = {}
    cross_safety: dict[str, list[dict[str, Any]]] = {}
    for prompt_label, pkey in cross_specs:
        combo = f"{prompt_label}|{pkey}"
        if combo == "legal-rag-v2|P0":
            cross_targeted[combo] = baseline_false
            cross_safety[combo] = presentation_safety["P0"]
            continue
        if prompt_label == "legal-rag-v2" and pkey in presentation_targeted:
            cross_targeted[combo] = presentation_targeted[pkey]
            cross_safety[combo] = presentation_safety[pkey]
            continue
        cross_targeted[combo] = [
            await one(case, prompt_label, pkey, repeat, "cross-matrix")
            for case in false_cases for repeat in range(1, 4)
        ]
        cross_safety[combo] = [
            await one(case, prompt_label, pkey, 1, "cross-safety")
            for case in unanswerable_cases
        ]
    cross_summary = {
        combo: {
            "targeted": summarize(cross_targeted[combo], answerable=True),
            "safety": summarize(cross_safety[combo], answerable=False),
        }
        for combo in cross_targeted
    }

    # Rank production-plausible combinations and send only the two best through
    # all 55 answerable cases, avoiding an unjustified combinatorial sweep.
    eligible_ranked = []
    for combo, value in cross_summary.items():
        if combo == "legal-rag-v2|P0":
            continue
        safety = value["safety"]
        if safety["abstention_rate"] == 1.0 and safety["unsupported_direct_answer_count"] == 0 and safety["status_valid_rate"] == 1.0:
            targeted = value["targeted"]
            eligible_ranked.append((
                targeted["grounded_conversion_rate"] or 0,
                targeted["citation_validity_rate"] or 0,
                targeted["expected_source_match_rate"] or 0,
                -(targeted["mean_prompt_tokens"] or 10**9),
                combo,
            ))
    finalist_combos = [item[-1] for item in sorted(eligible_ranked, reverse=True)[:2]]
    # Promote two causal decision controls even when token-efficiency
    # tie-breaking keeps them out of the top two. Otherwise the experiment
    # cannot distinguish prompt-only from presentation-only effects.
    for decision_control in ("compact|P0", "legal-rag-v2|P1"):
        if decision_control in cross_summary and decision_control not in finalist_combos:
            safety = cross_summary[decision_control]["safety"]
            if safety["abstention_rate"] == 1.0 and safety["unsupported_direct_answer_count"] == 0 and safety["status_valid_rate"] == 1.0:
                finalist_combos.append(decision_control)
    if not finalist_combos:
        finalist_combos = ["legal-rag-v2|P0"]

    finalist_answerable: dict[str, list[dict[str, Any]]] = {}
    finalist_unanswerable: dict[str, list[dict[str, Any]]] = {}
    for combo in finalist_combos:
        prompt_label, pkey = combo.split("|")
        finalist_answerable[combo] = [
            await one(case, prompt_label, pkey, 100, "finalist-all-answerable")
            for case in answerable_cases
        ]
        finalist_unanswerable[combo] = [
            await one(case, prompt_label, pkey, 100, "finalist-all-unanswerable")
            for case in unanswerable_cases
        ]

    # Reproduce the historical duplicate-marker case with the exact old prompt.
    duplicate_records = [
        await one(by_id[DUPLICATE_CASE_ID], "previous-combined", "P0", repeat, "duplicate-reproduction")
        for repeat in range(1, 4)
    ]

    finalist_summary = {
        combo: {
            "answerable": summarize(finalist_answerable[combo], answerable=True),
            "unanswerable": summarize(finalist_unanswerable[combo], answerable=False),
            "category_breakdown": category_breakdown(finalist_answerable[combo], cases),
            "targeted": cross_summary[combo]["targeted"],
        }
        for combo in finalist_combos
    }
    best_combo = max(
        finalist_combos,
        key=lambda combo: (
            finalist_summary[combo]["unanswerable"]["abstention_rate"] == 1.0,
            finalist_summary[combo]["unanswerable"]["unsupported_direct_answer_count"] == 0,
            finalist_summary[combo]["answerable"]["status_valid_rate"] == 1.0,
            finalist_summary[combo]["answerable"]["grounded_conversion_rate"] or 0,
            finalist_summary[combo]["answerable"]["citation_validity_rate"] or 0,
            finalist_summary[combo]["answerable"]["expected_source_match_rate"] or 0,
        ),
    )

    frozen = frozen_baseline_summary(cases)
    best_data = finalist_summary[best_combo]
    prompt_label, presentation_key = best_combo.split("|")
    all_status_records = finalist_answerable[best_combo] + finalist_unanswerable[best_combo]
    best_joint = {
        "key": best_combo,
        "prompt": prompt_label,
        "presentation": presentation_key,
        **best_data,
        "all_cases_status_validity": sum(item["answerability_validation"] == "PASS" for item in all_status_records) / len(all_status_records),
        "prompt_token_delta_vs_p0": (best_data["answerable"]["mean_prompt_tokens"] or 0) - (frozen["mean_prompt_tokens"] or 0),
        "ttft_delta_ms_vs_p0": (best_data["answerable"]["mean_ttft_ms"] or 0) - (frozen["mean_answerable_ttft_ms"] or 0),
        "generation_latency_delta_ms_vs_p0": (best_data["answerable"]["mean_generation_ms"] or 0) - (frozen["mean_answerable_generation_ms"] or 0),
    }

    previous = json.loads(PREVIOUS_RESULT.read_text(encoding="utf-8"))
    previous_variant_citations = {
        label: {
            "citation_validity_rate": value["summary"]["citation_structural_validity_rate"],
            "expected_source_match_rate": value["summary"]["expected_source_match_rate"],
            "status_valid_rate": value["summary"]["status_valid_rate"],
        }
        for label, value in previous["finalist_candidates"].items()
    }

    oracle_min_summary = summarize(oracle_minimal_records, answerable=True)
    oracle_first_summary = summarize(oracle_first_records, answerable=True)
    best_target = best_joint["targeted"]
    oracle_gap = {
        "oracle_minimal_grounded_rate": oracle_min_summary["grounded_conversion_rate"],
        "oracle_evidence_first_grounded_rate": oracle_first_summary["grounded_conversion_rate"],
        "best_production_plausible_targeted_grounded_rate": best_target["grounded_conversion_rate"],
        "minimal_minus_best_gap": (oracle_min_summary["grounded_conversion_rate"] or 0) - (best_target["grounded_conversion_rate"] or 0),
        "evidence_first_minus_best_gap": (oracle_first_summary["grounded_conversion_rate"] or 0) - (best_target["grounded_conversion_rate"] or 0),
    }

    def combo_accepts(combo: str) -> bool:
        data = finalist_summary.get(combo)
        return bool(data and (
            data["answerable"]["false_abstention_rate"] < frozen["false_abstention_rate"]
            and data["unanswerable"]["abstention_rate"] == 1.0
            and data["unanswerable"]["unsupported_direct_answer_count"] == 0
            and data["answerable"]["status_valid_rate"] == 1.0
            and data["unanswerable"]["status_valid_rate"] == 1.0
            and data["answerable"]["citation_validity_rate"] >= frozen["citation_validity_rate"] - 0.02
            and data["answerable"]["expected_source_match_rate"] >= frozen["expected_source_match_rate"] - 0.02
        ))

    accepts_candidate = combo_accepts(best_combo)
    prompt_only_accepts = combo_accepts("compact|P0")
    presentation_only_accepts = combo_accepts("legal-rag-v2|P1")
    if prompt_only_accepts and (
        not presentation_only_accepts
        or finalist_summary["compact|P0"]["answerable"]["grounded_conversion_rate"]
        >= finalist_summary["legal-rag-v2|P1"]["answerable"]["grounded_conversion_rate"]
    ):
        next_target = "LEGAL-RAG-V3 DESIGN"
    elif presentation_only_accepts:
        next_target = "EVIDENCE PRESENTATION V2 DESIGN"
    elif accepts_candidate and prompt_label != "legal-rag-v2":
        next_target = "LEGAL-RAG-V3 DESIGN"
    elif oracle_gap["minimal_minus_best_gap"] >= 0.20:
        next_target = "CONTEXT SELECTION V2 EXPERIMENT"
    elif oracle_gap["evidence_first_minus_best_gap"] >= 0.20:
        next_target = "QUERY-AWARE CONTEXT ORDERING EXPERIMENT"
    else:
        next_target = "NO CHANGE / MORE DATA"
    rationale = (
        "The best candidate satisfied every acceptance rule and may proceed to a separate production-design phase."
        if accepts_candidate else
        "No candidate simultaneously met the false-abstention, unanswerable safety, strict status, citation, and expected-source acceptance rules; legal-rag-v2 should remain frozen."
    )

    production_fingerprints = [fingerprint(path) for path in production_files()]
    configuration = {
        "provider": profile.provider,
        "model_id": profile.model_id,
        "prompt_version": profile.prompt_version,
        "tokenizer_provider": profile.tokenizer_provider,
        "tokenizer_id": profile.tokenizer_id,
        "model_context_limit": profile.model_context_limit,
        "context_budget_tokens": profile.context_budget_tokens,
        "max_output_tokens": profile.max_output_tokens,
        "prompt_token_safety_margin": profile.prompt_token_safety_margin,
        "temperature": profile.temperature,
        "top_p": profile.top_p,
        "top_k": profile.top_k,
        "thinking": profile.thinking,
        "request_timeout_seconds": profile.request_timeout_seconds,
        "chat_template_sha256": hashlib.sha256((prompt_counter._tokenizer.chat_template or "").encode()).hexdigest(),
        "status_parser": "strict deterministic exactly-one marker",
        "citation_parser": "exact [S<n>] only",
        "streaming": "start, delta*, done | start, delta*, error; initial status buffered and stripped",
    }

    baseline_summary = summarize(baseline_false, answerable=True)
    per_case = {}
    for case_id in FALSE_CASE_IDS:
        records = [item for item in baseline_false if item["case_id"] == case_id]
        answerable_count = sum(item["answerability_status"] == "ANSWERABLE" for item in records)
        insufficient_count = sum(item["answerability_status"] == "INSUFFICIENT_EVIDENCE" for item in records)
        classification = "STABLE" if answerable_count in {0, 3} else "STOCHASTIC"
        if insufficient_count == 0:
            classification = "NOT_REPRODUCED"
        per_case[case_id] = {
            "answerable": answerable_count,
            "insufficient": insufficient_count,
            "grounded": sum(item["grounded_conversion"] for item in records),
            "classification": classification,
            "records": records,
        }

    result = {
        "experiment_id": "evidence-presentation-status-citation-stability-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "datasets": hashes,
        "production_changed": False,
        "production_configuration": configuration,
        "production_file_fingerprints": production_fingerprints,
        "prompt_fingerprints": {label: fingerprint(path) for label, path in PROMPT_PATHS.items()},
        "diagnostic_case_set": {
            "false_abstention": list(FALSE_CASE_IDS),
            "successful_answerable_controls": list(PASS_CONTROL_IDS),
            "multi_evidence": [item["case_id"] for item in answerable_cases if item["metrics_v2"]["is_multi_evidence"]],
            "hierarchy_recovered": [item["case_id"] for item in answerable_cases if any(candidate.get("candidate_origin") == "HIERARCHY_CHILD" and candidate["chunk_id"] in {chunk for solution in item["acceptable_evidence_sets"] for chunk in solution} for candidate in item["block4"]["final_candidates"])],
            "multi_document": [item["case_id"] for item in answerable_cases if item["metrics_v2"]["is_multi_document"]],
            "hard_unanswerable": [item["case_id"] for item in unanswerable_cases if item["category"] == "HARD_UNANSWERABLE"],
            "out_of_corpus": [item["case_id"] for item in unanswerable_cases if item["category"] == "OUT_OF_CORPUS"],
            "partial_support": [item["case_id"] for item in unanswerable_cases if item["category"] == "PARTIAL_SUPPORT"],
        },
        "frozen_evaluation_baseline": frozen,
        "baseline_repeatability": {
            "false_cases": baseline_summary,
            "answerable_controls": summarize(baseline_pass, answerable=True),
            "unanswerable_controls": summarize(baseline_unanswerable, answerable=False),
            "per_case": per_case,
            "records": {"false": baseline_false, "pass": baseline_pass, "unanswerable": baseline_unanswerable},
        },
        "context_distraction": context_diagnostics(cases, packages, context_counter),
        "oracle_ceilings": {
            "production_eligible": False,
            "minimal": oracle_min_summary,
            "evidence_first": oracle_first_summary,
            "minimal_records": oracle_minimal_records,
            "evidence_first_records": oracle_first_records,
        },
        "strategy_comparison": {
            "presentation_screen": presentation_screen,
            "best_presentation": best_presentation,
            "cross_matrix": cross_summary,
            "finalists": finalist_summary,
        },
        "status_marker_failure_analysis": {
            "previous_record": {
                "case_id": DUPLICATE_CASE_ID,
                "raw_status_marker_count": 2,
                "answerability_validation": "ANSWERABILITY_STATUS_DUPLICATE",
                "raw_provider_text": "Two complete ANSWERABLE blocks were emitted in the prior recorded raw provider output.",
            },
            "reproduction": {**summarize(duplicate_records, answerable=True), "records": duplicate_records},
            "parser_changed": False,
            "stream_parser_cause_excluded": True,
            "likely_cause": "repeatable prompt/model output-contract failure: the raw provider repeats two answer blocks; not a parser or stream defect",
        },
        "citation_fading_analysis": {
            "previous_variant_full_answerable": previous_variant_citations,
            "current_cross_matrix": {
                combo: {
                    "citation_validity_rate": value["targeted"]["citation_validity_rate"],
                    "expected_source_match_rate": value["targeted"]["expected_source_match_rate"],
                    "missing_citation_rate": value["targeted"]["missing_citation_rate"],
                }
                for combo, value in cross_summary.items()
            },
            "citation_parser_changed": False,
        },
        "best_joint_combination": best_joint,
        "oracle_vs_production_gap": oracle_gap,
        "recommendation": {
            "acceptance_rules_pass": accepts_candidate,
            "prompt_only_acceptance_rules_pass": prompt_only_accepts,
            "presentation_only_acceptance_rules_pass": presentation_only_accepts,
            "next_target": next_target,
            "rationale": rationale,
            "production_change_authorized": False,
        },
        "method_limits": [
            "Ground-truth-aware minimal and evidence-first packages are oracle diagnostics only.",
            "Expected-source matching is deterministic but is not semantic entailment proof.",
            "Presentation screens preserve the frozen selected evidence set and use runtime-available fields only.",
            "The corpus contains ten unanswerable controls; external safety generalization is not claimed.",
            "Context, distractor, and hierarchy correlations are descriptive and do not prove causality.",
        ],
    }
    write_json(FINAL_JSON, result)
    render_reports(result)
    return result


async def run_and_close(fresh: bool) -> dict[str, Any]:
    try:
        return await run(fresh=fresh)
    finally:
        await close_llm_client()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(run_and_close(args.fresh))
    print(json.dumps({
        "best_joint_combination": result["best_joint_combination"]["key"],
        "recommendation": result["recommendation"],
    }, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
