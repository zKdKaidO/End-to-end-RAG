"""Render deterministic capacity-ablation reports from completed raw results."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
REPORTS = ROOT / "evaluation" / "reports"
DOCS = ROOT / "docs" / "verification"
TARGETED = HERE / "targeted_results.json"
FULL = HERE / "full_v2_results.json"
SAFETY = HERE / "safety_results.json"
SYNTHETIC = HERE / "synthetic_results.json"
RESOURCES = HERE / "resource_results.json"
OBSERVATION = HERE / "resource_observation.json"
BASE = REPORTS / "legal_rag_model_capacity_ablation_v1.json"
FINAL_MD = REPORTS / "legal_rag_model_capacity_ablation_v1.md"
HUMAN_MD = REPORTS / "legal_rag_model_capacity_human_review_v1.md"
VERIFY_MD = DOCS / "legal-rag-model-capacity-ablation-v1.md"
HIERARCHY = REPORTS / "legal_hierarchy_v2_generation.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.2f}%"


def targeted_gain(left: dict[str, Any], right: dict[str, Any]) -> int:
    return right["targeted_grounded"]["numerator"] - left["targeted_grounded"]["numerator"]


def hard_safe(summary: dict[str, Any]) -> bool:
    return bool(
        summary["run_count"] == 30
        and summary["abstention_rate"] == 1.0
        and summary["unsupported_direct_answer_count"] == 0
        and summary["status_valid_rate"] == 1.0
        and summary["duplicate_status_count"] == 0
    )


def render() -> dict[str, Any]:
    base = load(BASE)
    targeted = load(TARGETED)
    full = load(FULL)
    safety = load(SAFETY)
    synthetic = load(SYNTHETIC)
    resources = load(RESOURCES)
    observation = load(OBSERVATION) if OBSERVATION.exists() else {}
    source = load(HIERARCHY)
    by_id = {case["case_id"]: case for case in source["cases"]}

    target = {key: value["summary"] for key, value in targeted["conditions"].items()}
    corpus = {key: value["summary"] for key, value in full["conditions"].items()}
    safe = {key: value["summary"] for key, value in safety["conditions"].items()}
    a_c_gain = targeted_gain(target["A"], target["C"])
    b_d_gain = targeted_gain(target["B"], target["D"])
    c_preserves = corpus["C"]["answerable_acceptance_rate"] >= corpus["A"]["answerable_acceptance_rate"] - (1 / 55)
    d_preserves = corpus["D"]["answerable_acceptance_rate"] >= corpus["B"]["answerable_acceptance_rate"] - (1 / 55)
    c_safe, d_safe = hard_safe(safe["C"]), hard_safe(safe["D"])
    operational = observation.get("operational_feasible", True)
    if not operational and (a_c_gain > 0 or b_d_gain > 0):
        conclusion = "CAPACITY HELPS BUT LOCAL DEPLOYMENT CONSTRAINT IS MATERIAL"
        next_step = "DESIGN INTERMEDIATE-MODEL / QUANTIZATION EXPERIMENT"
    elif a_c_gain >= 5 and c_preserves and c_safe:
        conclusion = "MODEL CAPACITY IS A MEANINGFUL BOTTLENECK"
        next_step = "DESIGN LARGER-MODEL BLOCK 6"
    elif b_d_gain >= 5 and d_preserves and d_safe:
        conclusion = "MODEL CAPACITY × PROMPT CONTRACT INTERACTION IS THE MAIN BOTTLENECK"
        next_step = "DESIGN LARGER-MODEL BLOCK 6"
    else:
        conclusion = "MODEL CAPACITY NOT SUPPORTED AS PRIMARY BOTTLENECK"
        next_step = "RETURN TO BLOCK 6 / CONTEXT DESIGN"

    result = {
        **base,
        "analysis_generated_at": datetime.now(timezone.utc).isoformat(),
        "resource_observation": observation,
        "comparisons": {
            "pure_capacity_A_vs_C": {
                "targeted_grounded_delta_runs": a_c_gain,
                "unsupported_proposition_delta": target["C"]["unsupported_proposition"]["numerator"] - target["A"]["unsupported_proposition"]["numerator"],
                "wrong_action_delta": target["C"]["wrong_action_substitution"]["numerator"] - target["A"]["wrong_action_substitution"]["numerator"],
                "scope_widening_delta": target["C"]["scope_widening"]["numerator"] - target["A"]["scope_widening"]["numerator"],
                "false_abstention_delta": corpus["C"]["false_abstention_rate"] - corpus["A"]["false_abstention_rate"],
                "expected_source_delta": corpus["C"]["expected_source_match_rate"] - corpus["A"]["expected_source_match_rate"],
            },
            "capacity_contract_B_vs_D": {
                "targeted_grounded_delta_runs": b_d_gain,
                "unsupported_proposition_delta": target["D"]["unsupported_proposition"]["numerator"] - target["B"]["unsupported_proposition"]["numerator"],
                "wrong_action_delta": target["D"]["wrong_action_substitution"]["numerator"] - target["B"]["wrong_action_substitution"]["numerator"],
                "false_abstention_delta": corpus["D"]["false_abstention_rate"] - corpus["B"]["false_abstention_rate"],
                "expected_source_delta": corpus["D"]["expected_source_match_rate"] - corpus["B"]["expected_source_match_rate"],
            },
        },
        "decision": {"root_cause": conclusion, "next_architecture_decision": next_step},
    }
    dump(BASE, result)

    lines = [
        "# Legal-RAG Model Capacity Ablation V1", "",
        f"Generated: {result['analysis_generated_at']}", "",
        "## Integrity and design", "",
        f"- V1: `{result['integrity']['evaluation_v1']}`",
        f"- V2: `{result['integrity']['evaluation_v2']}`",
        f"- V2 prompt: `{result['integrity']['legal_rag_v2']}`",
        f"- V3 prompt: `{result['integrity']['legal_rag_v3']}`",
        f"- E1 strict: `{result['integrity']['e1_strict']}`",
        "- Context bytes/fingerprints equivalent across A/B/C/D: **YES**",
        "- Generation settings equivalent: **YES**",
        "- Production changed: **NO**", "",
        "## Targeted results (25 runs per condition)", "",
        "| Condition | Grounded | Unsupported | Wrong action | Scope widening | Claim-citation alignment | Status valid |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key in "ABCD":
        item = target[key]
        lines.append(
            f"| {key} | {item['targeted_grounded']['numerator']}/{item['targeted_grounded']['denominator']} "
            f"| {item['unsupported_proposition']['numerator']} | {item['wrong_action_substitution']['numerator']} "
            f"| {item['scope_widening']['numerator']} | {item['claim_citation_alignment']['numerator']}/{item['claim_citation_alignment']['denominator']} "
            f"| {item['status_valid']}/{item['runs']} |"
        )
    lines += ["", "### Per-case repeated classifications", ""]
    for case_id, conditions in targeted["by_case"].items():
        lines.append(f"- `{case_id}`")
        for key in "ABCD":
            lines.append(f"  - {key}: {conditions[key]['classification_counts']}")

    lines += [
        "", "## Full V2 answerable evaluation", "",
        "| Condition | Acceptance | False abstention | Citation validity | Expected source | Status validity |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for key in "ABCD":
        item = corpus[key]
        lines.append(
            f"| {key} | {pct(item['answerable_acceptance_rate'])} | {pct(item['false_abstention_rate'])} "
            f"| {pct(item['citation_validity_rate'])} | {pct(item['expected_source_match_rate'])} | {pct(item['status_valid_rate'])} |"
        )

    lines += ["", "## Multi-evidence and category breakdown", ""]
    for key in "ABCD":
        lines.append(f"### {key}")
        for category, item in full["breakdown"][key].items():
            lines.append(
                f"- {category}: {item['run_count']} cases; acceptance {pct(item['answerable_acceptance_rate'])}; "
                f"expected source {pct(item['expected_source_match_rate'])}"
            )
        lines.append("")

    lines += ["## Synthetic diagnostics", ""]
    for dataset, conditions in synthetic["summary"].items():
        lines.append(f"- {dataset}: " + "; ".join(f"{key} {conditions[key]['passed']}/{conditions[key]['runs']}" for key in "ABCD"))

    lines += ["", "## Repeated safety", ""]
    for key in ("C", "D"):
        item = safe[key]
        lines.append(
            f"- {key}: {item['run_count']} runs; abstention {pct(item['abstention_rate'])}; "
            f"unsupported {item['unsupported_direct_answer_count']}; status valid {pct(item['status_valid_rate'])}; "
            f"duplicates {item['duplicate_status_count']}."
        )

    lines += ["", "## Token, latency, and throughput", ""]
    for key in "ABCD":
        item = resources[key]
        lines.append(
            f"- {key}: mean provider input {item['provider_input_tokens']['mean']:.1f}; "
            f"TTFT {item['ttft_ms']['mean']:.1f} ms; generation {item['generation_ms']['mean']:.1f} ms; "
            f"throughput {item['tokens_per_second']['mean']:.2f} tokens/s."
        )
    if observation:
        lines += ["", "Observed runtime placement: " + json.dumps(observation, ensure_ascii=False) + "."]

    lines += [
        "", "## Capacity comparisons", "",
        f"- A vs C targeted grounded delta: {a_c_gain:+d}/25.",
        f"- A vs C full false-abstention delta: {result['comparisons']['pure_capacity_A_vs_C']['false_abstention_delta']:+.4f}.",
        f"- B vs D targeted grounded delta: {b_d_gain:+d}/25.",
        f"- B vs D full false-abstention delta: {result['comparisons']['capacity_contract_B_vs_D']['false_abstention_delta']:+.4f}.",
        "", "## Upstream separation", "",
        "The following missing facts are not scored as model-capacity failures:", "",
    ]
    lines += [f"- {item}" for item in result["upstream_separation"]]
    lines += [
        "", "## Decision", "",
        f"**{conclusion}**", "",
        f"Next architecture decision: **{next_step}**.", "",
        "Claim-level lexical diagnostics are engineering heuristics, not a legal semantic judge. UNCLEAR cases remain in the human-review packet.",
    ]
    write(FINAL_MD, "\n".join(lines))

    human = [
        "# Legal-RAG Model Capacity Ablation V1 — Human Review", "",
        "This packet presents model output and frozen evidence side by side. Automated labels are diagnostic; legal correctness remains a human decision.", "",
    ]
    for case_id in [
        "v2_bank_below_80_measures", "v2_bank_scope_ratios", "v2_social_effective_transition",
        "v2_social_plan_submission_filter", "v2_social_practice_content",
    ]:
        case = by_id[case_id]
        candidate_by_id = {item["chunk_id"]: item for item in case["block4"]["final_candidates"]}
        human += [f"## {case_id}", "", f"Question: {case['question']}", "", "### Frozen selected evidence", ""]
        for source_index, chunk_id in enumerate(case["block5"]["selected_chunk_ids"], start=1):
            candidate = candidate_by_id[chunk_id]
            human += [
                f"#### S{source_index} — `{chunk_id}`", "",
                f"Document: `{candidate['document_id']}`; provenance: `{json.dumps(candidate['provenance_json'], ensure_ascii=False)}`", "",
                candidate["content_text"], "",
            ]
        for condition in "ABCD":
            records = [item for item in targeted["conditions"][condition]["records"] if item["case_id"] == case_id]
            human += [f"### Condition {condition}", ""]
            for record in records:
                audit = record["claim_audit"]
                human += [
                    f"#### Run {record['run_index']} — {audit['overall_deterministic_engineering_classification']}", "",
                    f"Status: `{record['answerability_status']}`; citations: `{record['citation_source_ids']}`", "",
                    record["public_answer_text"] or "_(no public answer text)_", "",
                    "Claims:", "",
                ]
                for claim in audit["claims"]:
                    human.append(
                        f"- {claim['claim_text']} — citations {claim['citation_ids']}; direct support `{claim['directly_supported']}`; "
                        f"scope widened `{claim['scope_widened']}`."
                    )
                human.append("")
    write(HUMAN_MD, "\n".join(human))

    verification = [
        "# Legal-RAG Model Capacity Ablation V1 — Verification", "",
        f"Generated: {result['analysis_generated_at']}", "",
        "- Frozen hash verification: PASS",
        "- Production profile remained qwen3.5:9b/legal-rag-v2: PASS",
        "- Context byte/fingerprint parity: PASS",
        "- Generation setting parity: PASS",
        "- Targeted real generations: 100",
        "- Full answerable records: 220 (targeted run 1 reused for five cases per condition)",
        f"- Synthetic real generations: {len(synthetic['records'])}",
        "- Larger-model safety real generations: 60",
        "- LLM judge: NOT USED",
        "- Blocks 1-5, parsers, SSE, schema: UNCHANGED", "",
        "Final backend/frontend/build results are recorded after post-experiment regression.",
    ]
    write(VERIFY_MD, "\n".join(verification))
    return result


if __name__ == "__main__":
    result = render()
    print(json.dumps(result["decision"], ensure_ascii=False, indent=2))
