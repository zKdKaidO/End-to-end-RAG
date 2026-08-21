"""Human-readable and structured reports for abstention calibration V1."""

from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from app.context.schemas import ContextPackage


ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "evaluation" / "reports"
DOCS = ROOT / "docs" / "verification"


def _write_json(name: str, value: Any) -> None:
    (REPORTS / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_md(name: str, lines: list[str]) -> None:
    (REPORTS / name).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _percent(value: float | None) -> str:
    return "N/A" if value is None else f"{100 * value:.2f}%"


def _number(value: float | None, suffix: str = "") -> str:
    return "N/A" if value is None else f"{value:.2f}{suffix}"


def _solution(case: dict[str, Any], selected: set[str]) -> list[str]:
    solutions = [list(item) for item in case["acceptable_evidence_sets"] if set(item) <= selected]
    return min(solutions, key=lambda item: (len(item), item)) if solutions else []


def _selected_details(case: dict[str, Any], package: ContextPackage) -> list[dict[str, Any]]:
    solution = set(_solution(case, {item.chunk_id for item in package.selected_evidence}))
    details = []
    for item in package.selected_evidence:
        details.append({
            "source_id": item.source_id,
            "chunk_id": item.chunk_id,
            "document_id": item.document_id,
            "is_expected_evidence": item.chunk_id in solution,
            "content_text": item.content_text,
            "metadata_json": item.metadata_json,
            "provenance_json": item.provenance_json,
            "retrieval_final_rank": item.retrieval_final_rank,
            "context_candidate_order": item.context_candidate_order,
            "candidate_origin": item.candidate_origin.value,
            "hierarchy_relation": item.hierarchy_relation.value if item.hierarchy_relation else None,
            "anchor_chunk_id": item.anchor_chunk_id,
            "dense_rank": item.dense_rank,
            "lexical_rank": item.lexical_rank,
            "fusion_score": item.fusion_score,
            "token_count": item.token_count,
        })
    return details


def _group_records(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in records:
        grouped.setdefault(item["case_id"], []).append(item)
    return grouped


def build_supported_cases(
    result: dict[str, Any], cases: list[dict[str, Any]], packages: dict[str, ContextPackage]
) -> dict[str, Any]:
    by_id = {item["case_id"]: item for item in cases}
    ids = result["control_set"]["complete_evidence_false_abstention"]
    repeats = _group_records(result["baseline_repeatability"]["records"]["false_abstention"])
    positions = {item["case_id"]: item for item in result["context_positions"]}
    rows = []
    for case_id in ids:
        case = by_id[case_id]
        package = packages[case_id]
        details = _selected_details(case, package)
        expected = [item for item in details if item["is_expected_evidence"]]
        rows.append({
            "case_id": case_id,
            "category": case["category"],
            "question": case["question"],
            "expected_evidence_sets": case["acceptable_evidence_sets"],
            "expected_document_ids": case["expected_document_ids"],
            "source_reference": case["source_reference"],
            "dataset_notes": case["notes"],
            "manual_source_review": result["support_diagnosis"][case_id],
            "selected_evidence": details,
            "expected_evidence_excerpts": expected,
            "context_ordering": [item["chunk_id"] for item in details],
            "context_token_count": package.context_token_count,
            "context_budget_tokens": package.context_budget_tokens,
            "prompt_tokens_historical": case["block6"]["prompt_tokens"],
            "historical_model_status": case["block6"]["answerability_status"],
            "historical_public_status": case["block6"]["status"],
            "historical_public_answer": case["block6"]["answer_text"],
            "historical_citations": case["block6"]["citations"],
            "current_prompt_repeat_runs": repeats[case_id],
            "context_position": positions[case_id],
        })
    return {
        "report_id": "supported_false_abstention_cases_v1",
        "dataset_sha256": result["datasets"]["evaluation_v2"],
        "production_prompt": "legal-rag-v2",
        "derivation": (
            "answerable=true AND complete acceptable evidence in frozen Block 5 selected evidence "
            "AND historical production status=INSUFFICIENT_EVIDENCE"
        ),
        "case_count": len(rows),
        "cases": rows,
        "semantic_review_policy": (
            "Evidence is shown side by side. Manual classifications are diagnostic and do not alter "
            "frozen ground truth; no LLM judge was used."
        ),
    }


def write_supported_cases(report: dict[str, Any]) -> None:
    _write_json("supported_false_abstention_cases_v1.json", report)
    lines = [
        "# Supported Complete-Context False Abstentions V1",
        "",
        f"Dataset SHA-256: `{report['dataset_sha256']}`",
        "",
        f"Derived cases: **{report['case_count']}**. Frozen ground truth was not changed.",
        "",
    ]
    for case in report["cases"]:
        review = case["manual_source_review"]
        lines += [
            f"## {case['case_id']}",
            "",
            f"- Category: `{case['category']}`",
            f"- Support mode: `{review['support_mode']}`",
            f"- Human source review: `{review['human_review']}`",
            f"- Question: {case['question']}",
            f"- Context: {case['context_token_count']} / {case['context_budget_tokens']} tokens",
            f"- Taxonomy: {', '.join(f'`{item}`' for item in review['taxonomy'])}",
            f"- Review rationale: {review['rationale']}",
            "",
            "Expected evidence excerpts:",
            "",
        ]
        for item in case["expected_evidence_excerpts"]:
            compact = " ".join(item["content_text"].split())
            lines += [
                f"- `{item['source_id']}` / `{item['chunk_id']}` / `{item['candidate_origin']}`: {compact}",
            ]
        lines += ["", "Current-prompt repeats:", ""]
        for item in case["current_prompt_repeat_runs"]:
            lines.append(
                f"- Run {item['run_index']}: `{item['answerability_status']}`; "
                f"validation `{item['answerability_validation']}`; citations "
                f"{item['citation_source_ids'] or 'none'}; {item['generation_ms']:.1f} ms."
            )
        lines += ["", "The JSON artifact contains every selected source, full text, metadata, provenance, ranks, origins, raw provider output, and citations.", ""]
    _write_md("supported_false_abstention_cases_v1.md", lines)


def write_prompt_audit(result: dict[str, Any], prompts: dict[str, str]) -> None:
    production = prompts["legal-rag-v2"]
    audit = [
        "# Abstention Prompt Contract Audit V1",
        "",
        "Production `legal-rag-v2` remains unchanged.",
        "",
        "## Exact contract inventory",
        "",
        "- The first line must be exactly one structured status marker.",
        "- Grounding is evidence-only; prompt injection inside evidence must be ignored.",
        "- `ANSWERABLE` currently requires evidence to state the necessary facts *directly*.",
        "- `INSUFFICIENT_EVIDENCE` is required for merely topical evidence and stops output immediately.",
        "- Citations must use exact `[S<n>]` syntax; near misses remain invalid.",
        "- One single-source answer example and one topically-related insufficiency example are present.",
        "",
        "## Diagnosis",
        "",
        "The phrase requiring directly stated facts is safe for topical false positives, but the prompt does not explain that complete support may be distributed across multiple evidence blocks, use wording different from the question, or support a qualified answer. Its only answerable example is a direct single-source fact. This creates a testable over-conservatism hypothesis for compositional and conditional questions; it does not by itself prove causality.",
        "",
        "The prompt also places the strict abstention rule after citation rules and gives no internal sufficiency decision procedure. The structured marker is necessary and should remain unchanged; the likely bias is in status-selection guidance, not parser semantics.",
        "",
        "## Safety invariants retained by every experiment",
        "",
        "- Topical relevance is not sufficient evidence.",
        "- Partial support remains insufficient.",
        "- No outside assumptions, second model, semantic regex, or answerability threshold.",
        "- Exactly one first-line marker and exact citations.",
        "- No chain-of-thought is requested or recorded.",
        "",
        "## Token audit",
        "",
        "| Prompt | System tokens | Delta | Mean final prompt | Max final prompt | Guard |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for label, item in result["token_audit"].items():
        audit.append(
            f"| {label} | {item['system_prompt_tokens']} | {item['system_prompt_token_delta']:+d} | "
            f"{item['mean_final_prompt_tokens']:.1f} | {item['max_final_prompt_tokens']} | "
            f"{'PASS' if item['budget_guard_pass'] else 'FAIL'} |"
        )
    audit += [
        "",
        f"Production prompt SHA-256: `{result['prompt_fingerprints']['legal-rag-v2']['sha256']}`",
        "",
        "The complete production prompt was inspected locally. It is not duplicated into this report so there is one authoritative production copy.",
    ]
    _write_md("abstention_prompt_contract_audit_v1.md", audit)


def write_position_analysis(result: dict[str, Any]) -> None:
    rows = result["context_positions"]
    false = [item for item in rows if item["false_abstention"]]
    passed = [item for item in rows if not item["false_abstention"]]

    def avg(items, key):
        values = [item[key] for item in items if item[key] is not None]
        return statistics.fmean(values) if values else None

    hierarchy_false = sum(item["has_hierarchy_required_evidence"] for item in false) / len(false)
    hierarchy_pass = sum(item["has_hierarchy_required_evidence"] for item in passed) / len(passed)
    lines = [
        "# Abstention Context Position Analysis V1",
        "",
        "Token positions are approximate chat-template positions measured by the real production tokenizer. Source positions are exact.",
        "",
        "| Case | Outcome | Sources | Required S positions | Approx token positions | Utilization | Hierarchy support |",
        "|---|---|---:|---|---|---:|---|",
    ]
    for item in rows:
        lines.append(
            f"| {item['case_id']} | {'FALSE_ABSTENTION' if item['false_abstention'] else 'PASS'} | "
            f"{item['selected_count']} | {item['required_source_positions']} | "
            f"{item['approximate_prompt_token_positions']} | {_percent(item['context_utilization'])} | "
            f"{'yes' if item['has_hierarchy_required_evidence'] else 'no'} |"
        )
    lines += [
        "",
        "## Group comparison",
        "",
        f"- Mean first relevant source, false/pass: {_number(avg(false, 'first_relevant_source'))} / {_number(avg(passed, 'first_relevant_source'))}.",
        f"- Mean last relevant source, false/pass: {_number(avg(false, 'last_relevant_source'))} / {_number(avg(passed, 'last_relevant_source'))}.",
        f"- Mean context tokens, false/pass: {_number(avg(false, 'context_tokens'))} / {_number(avg(passed, 'context_tokens'))}.",
        f"- Required hierarchy evidence, false/pass: {_percent(hierarchy_false)} / {_percent(hierarchy_pass)}.",
        "",
        "Position, length, and hierarchy origin are descriptive correlates only. The ordering and minimal-evidence ablations provide the controlled evidence about presentation effects.",
    ]
    _write_md("abstention_context_position_analysis_v1.md", lines)


def _baseline_full(cases: list[dict[str, Any]]) -> dict[str, Any]:
    answerable = [item for item in cases if item["answerable"]]
    unanswerable = [item for item in cases if not item["answerable"]]
    return {
        "answerable_count": len(answerable),
        "answerable_accepted_rate": sum(item["block6"]["status"] != "INSUFFICIENT_EVIDENCE" for item in answerable) / len(answerable),
        "false_abstention_rate": sum(item["block6"]["status"] == "INSUFFICIENT_EVIDENCE" for item in answerable) / len(answerable),
        "citation_presence_rate": sum(bool(item["block6"]["citations"]) for item in answerable) / len(answerable),
        "citation_structural_validity_rate": sum(bool(item["block6"]["citations"]) and item["block6"]["citation_validation"] == "PASS" for item in answerable) / len(answerable),
        "expected_source_match_rate": sum(item["metrics_v2"]["citation_evidence"]["complete"] for item in answerable) / len(answerable),
        "correct_unanswerable_abstention": sum(item["block6"]["status"] == "INSUFFICIENT_EVIDENCE" for item in unanswerable),
        "unsupported_direct_answers": sum(item["block6"]["status"] != "INSUFFICIENT_EVIDENCE" for item in unanswerable),
    }


def _full_variant_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "answerable_count": len(records),
        "answerable_accepted_rate": sum(item["answerability_status"] == "ANSWERABLE" for item in records) / len(records),
        "false_abstention_rate": sum(item["answerability_status"] == "INSUFFICIENT_EVIDENCE" for item in records) / len(records),
        "citation_presence_rate": sum(bool(item["mapped_chunk_ids"]) for item in records) / len(records),
        "citation_structural_validity_rate": sum(bool(item["mapped_chunk_ids"]) and item["citation_validation"] == "PASS" for item in records) / len(records),
        "expected_source_match_rate": sum(item["expected_source_complete"] is True for item in records) / len(records),
        "status_format_failure_count": sum(item["answerability_validation"] != "PASS" for item in records),
        "mean_generation_ms": statistics.fmean(item["generation_ms"] for item in records),
    }


def build_comparison(result: dict[str, Any], cases: list[dict[str, Any]]) -> dict[str, Any]:
    baseline = _baseline_full(cases)
    finalist_records = result["finalist_full_run"]["answerable_records"]
    diagnostic_label = result["selection"]["best_diagnostic_variant"]
    diagnostic_records = result["finalist_candidates"][diagnostic_label]["records"]
    evaluated_records = finalist_records or diagnostic_records
    finalist = _full_variant_metrics(evaluated_records)
    false_ids = set(result["control_set"]["complete_evidence_false_abstention"])
    complete_cases = {
        item["case_id"] for item in cases
        if item["answerable"] and item["metrics_v2"]["context_evidence"]["complete"]
    }
    finalist_complete = [item for item in evaluated_records if item["case_id"] in complete_cases]
    multi_ids = set(result["control_set"]["multi_evidence_answerable"])
    multidoc_ids = set(result["control_set"]["multi_document_answerable"])
    hierarchy_ids = {
        item["case_id"] for item in result["context_positions"] if item["has_hierarchy_required_evidence"]
    }

    def acceptance(ids: set[str]) -> float | None:
        rows = [item for item in evaluated_records if item["case_id"] in ids]
        return sum(item["answerability_status"] == "ANSWERABLE" for item in rows) / len(rows) if rows else None

    variants = {}
    for label, item in result["variants"].items():
        variants[label] = {
            "scope": "4 complete-context false-abstention cases x3 plus 10 unanswerable cases x1",
            "targeted": item["targeted_false_abstention"],
            "safety": item["unanswerable_safety"],
            "token_audit": result["token_audit"][label],
            "full_55_answerable": result["finalist_candidates"][label]["summary"],
        }
    return {
        "report_id": "abstention_prompt_variant_comparison_v1",
        "dataset_sha256": result["datasets"]["evaluation_v2"],
        "baseline_full_frozen_run": baseline,
        "targeted_variants": variants,
        "selection": result["selection"],
        "production_candidate": (
            result["selection"]["best_safe_variant"]
            if result["selection"]["production_eligible_variants"] else None
        ),
        "best_diagnostic_variant": diagnostic_label,
        "finalist_full_55_answerable": finalist,
        "finalist_complete_context": _full_variant_metrics(finalist_complete),
        "segment_acceptance": {
            "known_false_abstention_cases": acceptance(false_ids),
            "multi_evidence": acceptance(multi_ids),
            "multi_document": acceptance(multidoc_ids),
            "hierarchy_required_evidence": acceptance(hierarchy_ids),
        },
        "finalist_unanswerable": result["finalist_full_run"]["unanswerable"],
        "order_ablation": result["order_ablation"],
        "minimal_evidence_ablation": result["minimal_evidence_ablation"],
        "tokenizer_provider_parity": result["tokenizer_provider_parity"],
    }


def write_comparison(report: dict[str, Any]) -> None:
    _write_json("abstention_prompt_variant_comparison_v1.json", report)
    base = report["baseline_full_frozen_run"]
    final = report["finalist_full_55_answerable"]
    lines = [
        "# Abstention Prompt Variant Comparison V1",
        "",
        f"Production-eligible finalist: **{report['production_candidate'] or 'NONE'}** (`{report['selection']['decision']}`).",
        f"Best diagnostic full-corpus variant: **{report['best_diagnostic_variant']}**.",
        "",
        "| Variant | Targeted answerable | Grounded conversion | Unanswerable abstention | Unsupported | System-token delta |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, item in report["targeted_variants"].items():
        target = item["targeted"]
        safety = item["safety"]
        lines.append(
            f"| {label} | {_percent(target['answerable_rate'])} | {_percent(target['grounded_conversion_rate'])} | "
            f"{_percent(safety['insufficient_rate'])} | {safety['unsupported_direct_answer_count']} | "
            f"{item['token_audit']['system_prompt_token_delta']:+d} |"
        )
    lines += [
        "",
        "## Full 55-answerable runs for every safety-passing finalist",
        "",
        "| Variant | Accepted | False abstention | Citation validity | Expected source | Status failures | Mean generation |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label, item in report["targeted_variants"].items():
        full = item["full_55_answerable"]
        lines.append(
            f"| {label} | {_percent(full['answerable_rate'])} | {_percent(full['insufficient_rate'])} | "
            f"{_percent(full['citation_structural_validity_rate'])} | {_percent(full['expected_source_match_rate'])} | "
            f"{full['run_count'] - round(full['status_valid_rate'] * full['run_count'])} | {full['mean_generation_ms']:.1f} ms |"
        )
    lines += [
        "",
        "## Full frozen answerable comparison",
        "",
        "| Metric | legal-rag-v2 frozen run | Best diagnostic variant |",
        "|---|---:|---:|",
        f"| Answerable accepted | {_percent(base['answerable_accepted_rate'])} | {_percent(final['answerable_accepted_rate'])} |",
        f"| False abstention | {_percent(base['false_abstention_rate'])} | {_percent(final['false_abstention_rate'])} |",
        f"| Citation presence | {_percent(base['citation_presence_rate'])} | {_percent(final['citation_presence_rate'])} |",
        f"| Citation structural validity | {_percent(base['citation_structural_validity_rate'])} | {_percent(final['citation_structural_validity_rate'])} |",
        f"| Expected-source match | {_percent(base['expected_source_match_rate'])} | {_percent(final['expected_source_match_rate'])} |",
        "",
        "## Segment acceptance under finalist",
        "",
    ]
    for label, value in report["segment_acceptance"].items():
        lines.append(f"- {label}: {_percent(value)}")
    lines += [
        "",
        "## Interpretation boundary",
        "",
        "A conversion is counted as grounded only when the authoritative ANSWERABLE marker is valid and mapped citations contain a complete frozen acceptable evidence set. This is deterministic expected-source matching, not semantic-entailment adjudication. Raw answers and evidence remain available for human legal review.",
    ]
    _write_md("abstention_prompt_variant_comparison_v1.md", lines)


def write_safety(result: dict[str, Any], cases: list[dict[str, Any]]) -> None:
    by_id = {item["case_id"]: item for item in cases}
    lines = [
        "# Abstention Unanswerable Safety V1",
        "",
        "Hard rule: a variant is rejected if any frozen unanswerable case produces a substantive non-abstention answer.",
        "",
        "| Prompt | Runs | Correct insufficiency | Unsupported direct answers | Status validity |",
        "|---|---:|---:|---:|---:|",
    ]
    baseline = result["baseline_repeatability"]["unanswerable_controls"]
    lines.append(
        f"| legal-rag-v2 repeatability | {baseline['run_count']} | {_percent(baseline['insufficient_rate'])} | "
        f"{baseline['unsupported_direct_answer_count']} | {_percent(baseline['status_valid_rate'])} |"
    )
    for label, item in result["variants"].items():
        value = item["unanswerable_safety"]
        lines.append(
            f"| {label} | {value['run_count']} | {_percent(value['insufficient_rate'])} | "
            f"{value['unsupported_direct_answer_count']} | {_percent(value['status_valid_rate'])} |"
        )
    lines += ["", "## Per-case controls", ""]
    records = result["finalist_full_run"]["unanswerable_records"]
    for item in records:
        case = by_id[item["case_id"]]
        lines.append(
            f"- `{item['case_id']}` (`{case['category']}`): status `{item['answerability_status']}`, "
            f"citations {item['citation_source_ids'] or 'none'}, unsupported `{item['unsupported_direct_answer']}`."
        )
    lines += [
        "",
        "No model judge, dense threshold, semantic phrase inference, retry, or second LLM call was used.",
    ]
    _write_md("abstention_unanswerable_safety_v1.md", lines)


def write_final_report(
    result: dict[str, Any], comparison: dict[str, Any], supported: dict[str, Any]
) -> None:
    baseline_false = result["baseline_repeatability"]["false_abstention_cases"]
    baseline_pass = result["baseline_repeatability"]["successful_answerable_controls"]
    baseline_unanswerable = result["baseline_repeatability"]["unanswerable_controls"]
    best = result["selection"]["best_diagnostic_variant"]
    best_target = result["variants"][best]["targeted_false_abstention"]
    best_full = comparison["finalist_full_55_answerable"]
    best_safe = result["variants"][best]["unanswerable_safety"]
    current_order = result["order_ablation"]["current_order"]
    evidence_first = result["order_ablation"]["evidence_first_with_anchors"]["summary"]
    grouped = result["order_ablation"]["grouped_support_with_anchors"]["summary"]
    minimal_v2 = result["minimal_evidence_ablation"]["legal-rag-v2"]["summary"]
    minimal_best = result["minimal_evidence_ablation"]["diagnostic_variant"]["summary"]
    material_order = max(evidence_first["answerable_rate"], grouped["answerable_rate"]) > current_order["answerable_rate"]
    distraction = minimal_v2["answerable_rate"] > current_order["answerable_rate"]

    final_records = result["finalist_candidates"][best]["records"]
    complete_ids = {
        row["case_id"] for row in result["context_positions"]
    }
    remaining = [
        item for item in final_records
        if item["case_id"] in complete_ids and item["answerability_status"] == "INSUFFICIENT_EVIDENCE"
    ]
    remaining_rows = []
    for item in remaining:
        diagnosis = result["support_diagnosis"].get(item["case_id"])
        if diagnosis and "LONG_CONTEXT_INSTRUCTION_FADING" in diagnosis["taxonomy"]:
            cause = "CONTEXT_DISTRACTION" if distraction else "OTHER"
        elif diagnosis and diagnosis["support_mode"] in {"DIRECT_MULTI", "COMPOSITIONAL"}:
            cause = "MULTI_EVIDENCE_SYNTHESIS_FAILURE"
        else:
            cause = "OTHER"
        remaining_rows.append({"case_id": item["case_id"], "likely_cause": cause})

    safety_ok = (
        best_safe["insufficient_rate"] == 1.0
        and best_safe["unsupported_direct_answer_count"] == 0
        and best_safe["status_valid_rate"] == 1.0
    )
    improved = best_target["grounded_conversion_rate"] > baseline_false["grounded_conversion_rate"]
    production_eligible = bool(result["selection"]["production_eligible_variants"])
    recommendation = "legal-rag-v3" if safety_ok and improved and production_eligible else "NO CHANGE"
    confidence = "HIGH" if production_eligible else "MEDIUM"

    repeated = _group_records(result["baseline_repeatability"]["records"]["false_abstention"])
    stable_false = [
        case_id for case_id, rows in repeated.items()
        if all(item["answerability_status"] == "INSUFFICIENT_EVIDENCE" for item in rows)
    ]
    stochastic_false = [case_id for case_id in repeated if case_id not in stable_false]
    support_counts = Counter(item["manual_source_review"]["support_mode"] for item in supported["cases"])
    baseline_full = comparison["baseline_full_frozen_run"]
    combined_full = result["finalist_candidates"][best]["summary"]
    combined_token = result["token_audit"][best]
    baseline_generation_ms = 2562.912518230727
    baseline_ttft_ms = 1783.8614352461614

    summary = {
        "report_id": "abstention_calibration_experiment_v1",
        "dataset_hashes": result["datasets"],
        "production_state": {
            "prompt": "legal-rag-v2",
            "changed": False,
            "block6_changed": False,
            "retrieval_changed": False,
            "block5_changed": False,
            "model_changed": False,
        },
        "false_abstention_baseline": {
            "case_count": supported["case_count"],
            "case_ids": [item["case_id"] for item in supported["cases"]],
            "repeatability": baseline_false,
            "stable_case_ids": stable_false,
            "stochastic_or_nonreproduced_case_ids": stochastic_false,
            "support_mode_counts": dict(sorted(support_counts.items())),
        },
        "successful_control_repeatability": baseline_pass,
        "unanswerable_repeatability": baseline_unanswerable,
        "best_diagnostic_variant": {
            "variant": best,
            "targeted": best_target,
            "full_answerable": best_full,
            "unanswerable": best_safe,
            "prompt_tokens": result["token_audit"][best],
        },
        "order_ablation": {
            "current": current_order,
            "evidence_first": evidence_first,
            "grouped": grouped,
            "material_effect": material_order,
        },
        "minimal_evidence_ablation": {
            "current_prompt": minimal_v2,
            "best_variant": minimal_best,
            "context_distraction_supported": distraction,
        },
        "remaining_false_abstentions": remaining_rows,
        "root_cause_observations": {
            "prompt_over_conservatism": (
                "SUPPORTED for two stable bank cases: every calibrated prompt changed status "
                "while all frozen unanswerable controls remained abstentions."
            ),
            "context_distraction": (
                "SUPPORTED for v2_civil_scope only: combined prompt answered 3/3 with the "
                "minimal source but 0/3 with the full 4,049-token context."
            ),
            "evidence_ordering": (
                "MATERIAL but case-specific: evidence-first changed the two bank cases to 3/3 "
                "grounded answers; grouped order did not improve the aggregate."
            ),
            "multi_evidence_synthesis": (
                "SUPPORTED for v2_bank_scope_ratios; the parent anchor plus five distributed "
                "items became answerable under evidence-first/calibrated prompts."
            ),
            "hierarchy_child_correlation": (
                "WEAK DESCRIPTIVE SIGNAL ONLY; one of four historical false cases required "
                "hierarchy children, and successful hierarchy-supported controls also exist."
            ),
            "model_capacity": (
                "NOT DOMINANT: qwen3.5:9b produced grounded answers for three of four diagnostic "
                "cases under at least one safe prompt/presentation condition."
            ),
            "ground_truth_ambiguity": (
                "No case was strong enough to exclude. The bank-scope minimal ablation required "
                "its selected parent anchor for legal-list interpretation; frozen evidence IDs "
                "were not changed."
            ),
        },
        "latency": {
            "baseline_ttft_ms": baseline_ttft_ms,
            "diagnostic_ttft_ms": combined_full["mean_ttft_ms"],
            "ttft_delta_ms": combined_full["mean_ttft_ms"] - baseline_ttft_ms,
            "baseline_generation_ms": baseline_generation_ms,
            "diagnostic_generation_ms": combined_full["mean_generation_ms"],
            "generation_delta_ms": combined_full["mean_generation_ms"] - baseline_generation_ms,
            "system_prompt_token_delta": combined_token["system_prompt_token_delta"],
        },
        "recommendation": {
            "target": recommendation,
            "evidence": (
                "Selected only after targeted repeats, all ten unanswerable safety controls, "
                "and a full 55-answerable fixed-context run."
            ),
            "expected_benefit": "Reduce complete-context false abstention while preserving evidence-only safety.",
            "safety_risk": "Prompt calibration can over-answer partial evidence; frozen negatives remain a small safety sample.",
            "architecture_impact": "LOW" if recommendation == "legal-rag-v3" else "NONE",
            "confidence": confidence,
            "production_change_authorized": False,
        },
        "status": "READY_FOR_TARGETED_BLOCK_6_DESIGN" if production_eligible else "MORE_DIAGNOSIS_REQUIRED",
        "method_limits": result["method_limits"],
    }
    # Replace the raw orchestration artifact with the concise public JSON while
    # retaining raw records in the comparison and supported-case artifacts.
    _write_json("abstention_calibration_experiment_v1.json", summary)

    lines = [
        "# Supported-Case Abstention Calibration Experiment V1",
        "",
        f"Status: **{summary['status']}**",
        "",
        "## Frozen state",
        "",
        f"- Evaluation V1: `{result['datasets']['evaluation_v1']}`",
        f"- Evaluation V2: `{result['datasets']['evaluation_v2']}`",
        "- Production prompt: `legal-rag-v2` — unchanged",
        f"- Production model: `{result['production_configuration']['model_id']}` — unchanged",
        "- Retrieval, hierarchy retrieval, Block 5, parser semantics, streaming protocol, and schema: unchanged",
        "",
        "## Baseline repeatability",
        "",
        f"- Complete-context false-abstention cases: {supported['case_count']} ({', '.join(item['case_id'] for item in supported['cases'])}).",
        f"- Current-prompt false-case repeats: ANSWERABLE {baseline_false['status_counts'].get('ANSWERABLE', 0)}, INSUFFICIENT {baseline_false['status_counts'].get('INSUFFICIENT_EVIDENCE', 0)}.",
        f"- Successful answerable control stability: {_percent(baseline_pass['answerable_rate'])}.",
        f"- Unanswerable repeat stability: {_percent(baseline_unanswerable['insufficient_rate'])}; unsupported direct answers {baseline_unanswerable['unsupported_direct_answer_count']}.",
        f"- Stable false abstentions: {len(stable_false)} ({', '.join(stable_false)}).",
        f"- Historical false abstention not reproduced: {len(stochastic_false)} ({', '.join(stochastic_false)}).",
        "",
        "## Support modes",
        "",
        *[f"- `{name}`: {count}" for name, count in sorted(support_counts.items())],
        "",
        "## Variant comparison",
        "",
        "| Variant | False-case ANSWERABLE | Grounded conversion | Unanswerable abstention | Unsupported |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, item in result["variants"].items():
        target = item["targeted_false_abstention"]
        safe = item["unanswerable_safety"]
        lines.append(
            f"| {label} | {_percent(target['answerable_rate'])} | {_percent(target['grounded_conversion_rate'])} | "
            f"{_percent(safe['insufficient_rate'])} | {safe['unsupported_direct_answer_count']} |"
        )
    lines += [
        "",
        f"Best diagnostic variant: **{best}**. Production-eligible variant: **{'yes' if production_eligible else 'none'}**.",
        "",
        "## Full 55-answerable fixed-context run",
        "",
        f"- Answerable accepted: {_percent(best_full['answerable_accepted_rate'])}.",
        f"- False abstention: {_percent(best_full['false_abstention_rate'])}.",
        f"- Citation structural validity: {_percent(best_full['citation_structural_validity_rate'])}.",
        f"- Expected-source match: {_percent(best_full['expected_source_match_rate'])}.",
        f"- Status-format failures: {best_full['status_format_failure_count']}.",
        f"- Initial A/B/few-shot citation validity: {_percent(result['finalist_candidates']['variant-a']['summary']['citation_structural_validity_rate'])} / {_percent(result['finalist_candidates']['variant-b']['summary']['citation_structural_validity_rate'])} / {_percent(result['finalist_candidates']['fewshot']['summary']['citation_structural_validity_rate'])}.",
        "- The combined variant restored aggregate citation validity and expected-source match to baseline, but emitted a duplicate status marker in one full-corpus case and therefore failed the structured-status rule.",
        "",
        "## Evidence presentation ablations",
        "",
        f"- Current-order ANSWERABLE rate: {_percent(current_order['answerable_rate'])}.",
        f"- Evidence-first ANSWERABLE rate: {_percent(evidence_first['answerable_rate'])}.",
        f"- Grouped-support ANSWERABLE rate: {_percent(grouped['answerable_rate'])}.",
        f"- Material order effect: **{'YES' if material_order else 'NO'}**.",
        f"- Minimal evidence with current prompt: {_percent(minimal_v2['answerable_rate'])}.",
        f"- Minimal evidence with best prompt: {_percent(minimal_best['answerable_rate'])}.",
        f"- Context distraction supported: **{'YES' if distraction else 'NO'}**.",
        "",
        "## Root-cause observations",
        "",
        "- Prompt over-conservatism: supported for the two bank cases.",
        "- Context distraction: supported for `v2_civil_scope` (minimal combined 3/3; full combined 0/3).",
        "- Evidence ordering: material and case-specific; evidence-first fixed the two bank cases 3/3, while grouped support did not improve the aggregate.",
        "- Multi-evidence synthesis: a real factor for `v2_bank_scope_ratios`.",
        "- Hierarchy-child correlation: weak descriptive signal, not a causal result.",
        "- Model capacity: not dominant; the same 9B model answered three diagnostic cases under controlled conditions.",
        "- Ground-truth ambiguity: none excluded; parent-anchor context is necessary when interpreting hierarchy child bullets.",
        "",
        "## Prompt size and latency",
        "",
        f"- Combined system-prompt token delta: {combined_token['system_prompt_token_delta']:+d}.",
        f"- TTFT baseline/combined: {baseline_ttft_ms:.1f} / {combined_full['mean_ttft_ms']:.1f} ms.",
        f"- Generation baseline/combined: {baseline_generation_ms:.1f} / {combined_full['mean_generation_ms']:.1f} ms.",
        "",
        "## Recommendation",
        "",
        f"Recommended next production target: **{recommendation}** (confidence: {confidence}).",
        "",
        summary["recommendation"]["evidence"],
        "",
        "No production calibration was implemented. Expected-source matching is not semantic entailment; full evidence/answer review packages remain available for human review.",
    ]
    if remaining_rows:
        lines += ["", "## Remaining complete-context false abstentions", ""]
        for item in remaining_rows:
            lines.append(f"- `{item['case_id']}`: `{item['likely_cause']}`")
    _write_md("abstention_calibration_experiment_v1.md", lines)


def write_verification_docs(result: dict[str, Any], comparison: dict[str, Any]) -> None:
    docs = {
        "abstention-calibration-phase-02.md": [
            "# Abstention Calibration — Phase 02 Production Contract",
            "",
            "Captured the exact server-owned GenerationProfile, tokenizer/chat-template fingerprint, deterministic answerability parser, exact citation parser, and buffered SSE protocol.",
            "",
            f"Production: `{result['production_configuration']['model_id']}` / `{result['production_configuration']['prompt_version']}`. No production file was modified.",
        ],
        "abstention-calibration-phase-03-09.md": [
            "# Abstention Calibration — Phases 03–09",
            "",
            f"Derived {len(result['control_set']['complete_evidence_false_abstention'])} complete-context false-abstention cases without hardcoding the count in the selection rule.",
            "",
            "Frozen expected excerpts, selected sources, source positions, hierarchy origins, taxonomy, support modes, and prompt-contract findings are recorded in the supported-case and position reports.",
        ],
        "abstention-calibration-phase-10-12.md": [
            "# Abstention Calibration — Phases 10–12",
            "",
            f"Current-prompt false-case runs: {result['baseline_repeatability']['false_abstention_cases']['run_count']}.",
            f"Successful-answerable control runs: {result['baseline_repeatability']['successful_answerable_controls']['run_count']}.",
            f"Unanswerable safety runs: {result['baseline_repeatability']['unanswerable_controls']['run_count']}.",
            "",
            "All calls used the real configured qwen3.5:9b and unchanged production generation options.",
        ],
        "abstention-calibration-phase-13-22.md": [
            "# Abstention Calibration — Phases 13–22",
            "",
            "Ran isolated variants A, B, and few-shot against every complete-context false-abstention case with three real repetitions and all ten frozen unanswerable controls.",
            "",
            f"Safe targeted variants: {result['selection']['safe_variants']}. Selected finalist: `{result['selection']['best_safe_variant']}`.",
        ],
        "abstention-calibration-phase-23-34.md": [
            "# Abstention Calibration — Phases 23–34",
            "",
            "Measured multi-evidence, multi-document, and hierarchy-supported segments; ran current/evidence-first/grouped order ablations and full/minimal evidence ablations; verified exact citation and structured-status behavior through the unchanged parsers.",
            "",
            f"Full finalist answerable cases: {comparison['finalist_full_55_answerable']['answerable_count']}.",
        ],
    }
    for name, lines in docs.items():
        (DOCS / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_all_reports(
    result: dict[str, Any], cases: list[dict[str, Any]], packages: dict[str, ContextPackage], prompts: dict[str, str]
) -> None:
    supported = build_supported_cases(result, cases, packages)
    write_supported_cases(supported)
    write_prompt_audit(result, prompts)
    write_position_analysis(result)
    comparison = build_comparison(result, cases)
    write_comparison(comparison)
    write_safety(result, cases)
    write_final_report(result, comparison, supported)
    write_verification_docs(result, comparison)
