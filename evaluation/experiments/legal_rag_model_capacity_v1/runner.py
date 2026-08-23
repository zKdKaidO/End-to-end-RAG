"""Controlled 2 x 2 local model-capacity ablation.

No prompt is registered and no production profile is mutated. Every condition
receives the same frozen P0 Block 5 ContextPackage bytes.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import statistics
import time
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from app.context.service import ContextBuilderService
from app.generation.profile import get_generation_profile
from app.generation.runtime import close_llm_client, get_llm_client
from app.generation.tokenizers import ContextTokenCounter, PromptTokenCounter
from evaluation.experiments.evidence_presentation_v1.presentation import PRESENTATIONS, user_content
from evaluation.experiments.evidence_presentation_v1.runner import (
    build_package,
    category_breakdown,
    generate_once,
    sha256,
    summarize,
)
from evaluation.experiments.legal_rag_v3_grounding_v1.runner import (
    audit_target,
    generate_synthetic_once,
    paired_outcomes,
    score_synthetic,
    synthetic_summary as _unused_synthetic_summary,
    target_summary,
)


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
REPORTS = ROOT / "evaluation" / "reports"
DATASET_V1 = ROOT / "evaluation" / "datasets" / "legal_eval_v1.json"
DATASET_V2 = ROOT / "evaluation" / "datasets" / "legal_eval_v2.json"
V2_PROMPT = ROOT / "app" / "prompts" / "legal-rag-v2.txt"
V3_PROMPT = ROOT / "app" / "prompts" / "legal-rag-v3.txt"
E1_PROMPT = ROOT / "evaluation" / "experiments" / "legal_rag_v3_grounding_v1" / "e1_strict.txt"
HIERARCHY = REPORTS / "legal_hierarchy_v2_generation.json"
PROGRESS = HERE / "raw_progress.json"
CONTEXTS = HERE / "context_fingerprints.json"
TARGETED = HERE / "targeted_results.json"
FULL = HERE / "full_v2_results.json"
SAFETY = HERE / "safety_results.json"
SYNTHETIC = HERE / "synthetic_results.json"

FROZEN = {
    "evaluation_v1": (DATASET_V1, "afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245"),
    "evaluation_v2": (DATASET_V2, "ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842"),
    "legal_rag_v2": (V2_PROMPT, "a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee"),
    "legal_rag_v3": (V3_PROMPT, "35b0abd69608ef574ac7bbf5c314eadb6ef9decd0dda3dd60e0a170aad243ebf"),
    "e1_strict": (E1_PROMPT, "ae7d35a85fdd5db661ed43b198c9dc67c6c6e2513b5a8b3989f83c963bd83da2"),
}
CONDITIONS = {
    "A": {"model": "qwen3.5:9b", "prompt_variant": "E0", "prompt": V3_PROMPT},
    "B": {"model": "qwen3.5:9b", "prompt_variant": "E1", "prompt": E1_PROMPT},
    "C": {"model": "qwen3.5:27b", "prompt_variant": "E0", "prompt": V3_PROMPT},
    "D": {"model": "qwen3.5:27b", "prompt_variant": "E1", "prompt": E1_PROMPT},
}
TARGET_IDS = (
    "v2_bank_below_80_measures",
    "v2_bank_scope_ratios",
    "v2_social_effective_transition",
    "v2_social_plan_submission_filter",
    "v2_social_practice_content",
)
SYNTHETIC_PATHS = {
    "partial_coverage": ROOT / "evaluation" / "experiments" / "legal_rag_v3_grounding_v1" / "synthetic_partial_coverage.json",
    "action_disambiguation": ROOT / "evaluation" / "experiments" / "legal_rag_v3_grounding_v1" / "synthetic_action_disambiguation.json",
    "citation_alignment": ROOT / "evaluation" / "experiments" / "legal_rag_v3_grounding_v1" / "synthetic_citation_alignment.json",
}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


class ProgressStore:
    def __init__(self, fresh: bool) -> None:
        if fresh and PROGRESS.exists():
            PROGRESS.unlink()
        self.records: dict[str, dict[str, Any]] = {}
        if PROGRESS.exists():
            data = json.loads(PROGRESS.read_text(encoding="utf-8"))
            self.records = {item["checkpoint_key"]: item for item in data.get("records", [])}

    def save(self) -> None:
        write_json(PROGRESS, {
            "experiment": "legal-rag-model-capacity-ablation-v1",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "records": list(self.records.values()),
        })

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


def mean(values: list[float | int | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return statistics.fmean(clean) if clean else None


def distribution(values: list[float | int | None]) -> dict[str, Any]:
    clean = [float(value) for value in values if value is not None]
    return {
        "count": len(clean),
        "mean": mean(clean),
        "min": min(clean) if clean else None,
        "max": max(clean) if clean else None,
    }


def token_rate(record: dict[str, Any]) -> float | None:
    usage = record.get("provider_usage") or {}
    output = usage.get("output_tokens")
    duration = record.get("generation_ms")
    return output / (duration / 1000) if isinstance(output, int) and duration else None


def synthetic_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for dataset in SYNTHETIC_PATHS:
        result[dataset] = {}
        for condition in CONDITIONS:
            items = [item for item in records if item["dataset"] == dataset and item["condition"] == condition]
            result[dataset][condition] = {
                "runs": len(items),
                "passed": sum(item["diagnostic_score"]["passed"] for item in items),
                "failed": sum(not item["diagnostic_score"]["passed"] for item in items),
                "status_valid": sum(item["diagnostic_score"]["valid_marker"] for item in items),
                "failure_reasons": dict(sorted(Counter(
                    reason for item in items for reason in item["diagnostic_score"]["failure_reasons"]
                ).items())),
            }
    return result


async def run(fresh: bool, contexts_only: bool = False) -> dict[str, Any]:
    integrity = {name: sha256(path) for name, (path, _) in FROZEN.items()}
    expected = {name: digest for name, (_, digest) in FROZEN.items()}
    if integrity != expected:
        raise RuntimeError(f"frozen integrity mismatch: {integrity}")

    source = json.loads(HIERARCHY.read_text(encoding="utf-8"))
    cases = source["cases"]
    answerable = [case for case in cases if case["answerable"]]
    unanswerable = [case for case in cases if not case["answerable"]]
    if len(cases) != 65 or len(answerable) != 55 or len(unanswerable) != 10:
        raise RuntimeError("frozen V2 case counts changed")
    by_id = {case["case_id"]: case for case in cases}

    production = get_generation_profile()
    if production.model_id != "qwen3.5:9b" or production.prompt_version != "legal-rag-v2":
        raise RuntimeError("production profile is no longer qwen3.5:9b/legal-rag-v2")
    profiles = {key: replace(production, model_id=value["model"]) for key, value in CONDITIONS.items()}
    for profile in profiles.values():
        profile.validate()

    context_counter = ContextTokenCounter(production.tokenizer_provider, production.tokenizer_id)
    prompt_counter = PromptTokenCounter(production.tokenizer_provider, production.tokenizer_id, thinking=production.thinking)
    builder = ContextBuilderService(context_counter)
    packages = {case["case_id"]: build_package(case, builder, production) for case in cases}
    context_rows = []
    for case in cases:
        package = packages[case["case_id"]]
        selected = [item.chunk_id for item in package.selected_evidence]
        if selected != case["block5"]["selected_chunk_ids"]:
            raise RuntimeError(f"{case['case_id']}: frozen P0 context drift")
        rendered = user_content(package, PRESENTATIONS["P0"].user_boundary)
        context_rows.append({
            "case_id": case["case_id"],
            "sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
            "utf8_bytes": len(rendered.encode("utf-8")),
            "selected_source_ids": [item.source_id for item in package.selected_evidence],
            "selected_chunk_ids": selected,
            "context_tokens": package.context_token_count,
            "identical_for_conditions": list(CONDITIONS),
        })
    write_json(CONTEXTS, {
        "presentation": "P0",
        "byte_equivalent_across_conditions": True,
        "tokenizer": production.tokenizer_id,
        "cases": context_rows,
    })
    if contexts_only:
        return {
            "integrity": integrity,
            "production": {"model": production.model_id, "prompt": production.prompt_version, "changed": False},
            "context_parity": {"byte_equivalent": True, "case_count": len(context_rows)},
        }

    prompts = {key: value["prompt"].read_text(encoding="utf-8").strip() for key, value in CONDITIONS.items()}
    store = ProgressStore(fresh)
    client = get_llm_client()
    for key in CONDITIONS:
        await client.health(profiles[key])

    async def real_one(case: dict[str, Any], condition: str, repeat: int, purpose: str) -> dict[str, Any]:
        spec = CONDITIONS[condition]
        prompt_hash = expected["legal_rag_v3"] if spec["prompt_variant"] == "E0" else expected["e1_strict"]
        key = f"{purpose}|{condition}|{spec['model']}|{prompt_hash}|P0|{case['case_id']}|{repeat}"

        async def factory() -> dict[str, Any]:
            record = await generate_once(
                case=case,
                package=packages[case["case_id"]],
                prompt_label=condition,
                prompt=prompts[condition],
                presentation=PRESENTATIONS["P0"],
                run_index=repeat,
                purpose=purpose,
                profile=profiles[condition],
                context_counter=context_counter,
                prompt_counter=prompt_counter,
                client=client,
            )
            record.update({
                "condition": condition,
                "variant": spec["prompt_variant"],
                "model_id": spec["model"],
                "prompt_sha256": prompt_hash,
                "context_sha256": next(row["sha256"] for row in context_rows if row["case_id"] == case["case_id"]),
            })
            return record

        return await store.ensure(key, factory)

    targeted_records: dict[str, list[dict[str, Any]]] = {}
    for condition in CONDITIONS:
        records = [
            await real_one(by_id[case_id], condition, repeat, "targeted-5x")
            for case_id in TARGET_IDS for repeat in range(1, 6)
        ]
        for record in records:
            record["claim_audit"] = audit_target(record, packages[record["case_id"]])
        targeted_records[condition] = records
    targeted_payload = {
        "conditions": {
            key: {"summary": target_summary(value), "records": value}
            for key, value in targeted_records.items()
        },
        "by_case": {
            case_id: {
                condition: target_summary([record for record in records if record["case_id"] == case_id])
                for condition, records in targeted_records.items()
            }
            for case_id in TARGET_IDS
        },
    }
    write_json(TARGETED, targeted_payload)

    full_records: dict[str, list[dict[str, Any]]] = {}
    for condition in CONDITIONS:
        target_run_one = {record["case_id"]: record for record in targeted_records[condition] if record["run_index"] == 1}
        records = [
            target_run_one.get(case["case_id"])
            or await real_one(case, condition, 1, "full-answerable")
            for case in answerable
        ]
        full_records[condition] = records
    full_payload = {
        "conditions": {
            key: {"summary": summarize(value, answerable=True), "records": value}
            for key, value in full_records.items()
        },
        "breakdown": {
            key: {
                **category_breakdown(records, cases),
                "partial_qualified": summarize(
                    [record for record in records if by_id[record["case_id"]]["category"] == "PARTIAL_SUPPORT"],
                    answerable=True,
                ),
            }
            for key, records in full_records.items()
        },
        "paired": {
            "A_vs_C_acceptance": paired_outcomes(full_records["A"], full_records["C"], lambda x: x["answerability_status"] == "ANSWERABLE"),
            "B_vs_D_acceptance": paired_outcomes(full_records["B"], full_records["D"], lambda x: x["answerability_status"] == "ANSWERABLE"),
            "A_vs_C_expected_source": paired_outcomes(full_records["A"], full_records["C"], lambda x: x["expected_source_complete"] is True),
            "B_vs_D_expected_source": paired_outcomes(full_records["B"], full_records["D"], lambda x: x["expected_source_complete"] is True),
        },
    }
    write_json(FULL, full_payload)

    synthetic_cases = {
        name: json.loads(path.read_text(encoding="utf-8"))["cases"]
        for name, path in SYNTHETIC_PATHS.items()
    }
    synthetic_records = []
    for condition, spec in CONDITIONS.items():
        for dataset, dataset_cases in synthetic_cases.items():
            for case in dataset_cases:
                prompt_hash = expected["legal_rag_v3"] if spec["prompt_variant"] == "E0" else expected["e1_strict"]
                key = f"synthetic|{condition}|{spec['model']}|{prompt_hash}|{dataset}|{case['case_id']}|1"

                async def factory(case=case, dataset=dataset, condition=condition, spec=spec):
                    record = await generate_synthetic_once(
                        dataset=dataset,
                        case=case,
                        variant=spec["prompt_variant"],
                        prompt=prompts[condition],
                        profile=profiles[condition],
                        counter=prompt_counter,
                        client=client,
                    )
                    record.update({"condition": condition, "model_id": spec["model"]})
                    return record

                record = await store.ensure(key, factory)
                record["diagnostic_score"] = score_synthetic(record, case)
                synthetic_records.append(record)
    synthetic_payload = {"summary": synthetic_summary(synthetic_records), "records": synthetic_records}
    write_json(SYNTHETIC, synthetic_payload)

    safety_records: dict[str, list[dict[str, Any]]] = {}
    for condition in ("C", "D"):
        safety_records[condition] = [
            await real_one(case, condition, repeat, "safety-3x")
            for case in unanswerable for repeat in range(1, 4)
        ]
    safety_payload = {
        "candidate_conditions": ["C", "D"],
        "conditions": {
            key: {"summary": summarize(value, answerable=False), "records": value}
            for key, value in safety_records.items()
        },
    }
    write_json(SAFETY, safety_payload)

    all_records = {
        condition: targeted_records[condition]
        + [item for item in full_records[condition] if item["case_id"] not in TARGET_IDS]
        + safety_records.get(condition, [])
        + [item for item in synthetic_records if item["condition"] == condition]
        for condition in CONDITIONS
    }
    resource = {
        condition: {
            "calls": len(records),
            "prompt_tokens": distribution([item.get("prompt_tokens") for item in records]),
            "provider_input_tokens": distribution([(item.get("provider_usage") or {}).get("input_tokens") for item in records]),
            "provider_output_tokens": distribution([(item.get("provider_usage") or {}).get("output_tokens") for item in records]),
            "provider_prompt_token_delta": distribution([item.get("provider_prompt_token_delta") for item in records]),
            "ttft_ms": distribution([item.get("ttft_ms") for item in records]),
            "generation_ms": distribution([item.get("generation_ms") for item in records]),
            "total_call_ms": distribution([item.get("experiment_total_ms") for item in records]),
            "tokens_per_second": distribution([token_rate(item) for item in records]),
        }
        for condition, records in all_records.items()
    }
    write_json(HERE / "resource_results.json", resource)

    result = {
        "experiment": "legal-rag-model-capacity-ablation-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "integrity": integrity,
        "production": {"model": production.model_id, "prompt": production.prompt_version, "changed": False},
        "configuration": {
            key: {
                "model": spec["model"],
                "prompt_variant": spec["prompt_variant"],
                "prompt_sha256": expected["legal_rag_v3"] if spec["prompt_variant"] == "E0" else expected["e1_strict"],
                "temperature": profiles[key].temperature,
                "top_p": profiles[key].top_p,
                "top_k": profiles[key].top_k,
                "thinking": profiles[key].thinking,
                "max_output_tokens": profiles[key].max_output_tokens,
                "model_context_limit": profiles[key].model_context_limit,
                "provider": profiles[key].provider,
                "tokenizer": profiles[key].tokenizer_id,
            }
            for key, spec in CONDITIONS.items()
        },
        "context_parity": {"byte_equivalent": True, "case_count": len(context_rows)},
        "targeted": {key: value["summary"] for key, value in targeted_payload["conditions"].items()},
        "full": {key: value["summary"] for key, value in full_payload["conditions"].items()},
        "breakdown": full_payload["breakdown"],
        "synthetic": synthetic_payload["summary"],
        "safety": {key: value["summary"] for key, value in safety_payload["conditions"].items()},
        "resources": resource,
        "upstream_separation": [
            "v2_social_effective_transition: effective-date evidence absent",
            "v2_bank_actual_capital_formula: expected formula evidence absent",
            "v2_social_applicable_groups: required group evidence absent",
        ],
    }
    write_json(REPORTS / "legal_rag_model_capacity_ablation_v1.json", result)
    return result


async def run_and_close(fresh: bool, contexts_only: bool = False) -> dict[str, Any]:
    try:
        return await run(fresh, contexts_only)
    finally:
        await close_llm_client()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--contexts-only", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(run_and_close(args.fresh, args.contexts_only))
    if args.contexts_only:
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        return
    print(json.dumps({
        "targeted": result["targeted"],
        "full": result["full"],
        "safety": result["safety"],
    }, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
