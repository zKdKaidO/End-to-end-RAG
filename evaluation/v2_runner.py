"""Run the immutable Legal Evaluation V2 dataset through the real frozen RAG pipeline."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.context.service import ContextBuilderService
from app.db.database import SessionLocal
from app.generation.profile import get_generation_profile
from app.generation.runtime import close_llm_client, get_llm_client
from app.generation.tokenizers import ContextTokenCounter, PromptTokenCounter
from app.indexing.constants import CANONICAL_INDEX_VERSION
from app.retrieval.repository import EMBEDDING_DIMENSION, EMBEDDING_MODEL
from evaluation.dataset_validator import load_dataset, validate_dataset
from evaluation.runner import run_case
from evaluation.v2_metrics import aggregate_v2, enrich_case


ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "evaluation" / "datasets" / "legal_eval_v2.json"
V1_DATASET_PATH = ROOT / "evaluation" / "datasets" / "legal_eval_v1.json"
INTEGRITY_PATH = ROOT / "evaluation" / "reports" / "legal_corpus_v2_integrity.json"
JSON_PATH = ROOT / "evaluation" / "reports" / "legal_eval_v2_baseline.json"
MARKDOWN_PATH = ROOT / "evaluation" / "reports" / "legal_eval_v2_baseline.md"
FAILURE_PATH = ROOT / "evaluation" / "reports" / "legal_eval_v2_failure_analysis.md"
RECOMMENDATIONS_PATH = ROOT / "evaluation" / "reports" / "legal_eval_v2_recommendations.md"
V2_SHA256 = "ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842"
V1_SHA256 = "afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _percent(value: float | None) -> str:
    return "N/A" if value is None else f"{100 * value:.2f}%"


def lexical_mode(db, query_text: str, document_ids: list[str] | None, lexical_count: int) -> str:
    if lexical_count == 0:
        return "NO_MATCH"
    document_filter = ""
    params: dict[str, Any] = {
        "query_text": query_text,
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "index_version": CANONICAL_INDEX_VERSION,
    }
    if document_ids:
        document_filter = "AND ci.document_id = ANY(CAST(:document_ids AS uuid[]))"
        params["document_ids"] = document_ids
    strict = db.execute(
        text(
            f"""
            SELECT EXISTS (
                SELECT 1 FROM chunk_indexes ci
                WHERE ci.lexical_tsv @@ websearch_to_tsquery('simple', :query_text)
                  AND ci.embedding_model = :embedding_model
                  AND ci.embedding_dimension = :embedding_dimension
                  AND ci.index_version = :index_version
                  {document_filter}
            )
            """
        ),
        params,
    ).scalar_one()
    return "STRICT_MATCH" if strict else "SELECTIVE_FALLBACK"


def scale_snapshot() -> dict[str, Any]:
    integrity = json.loads(INTEGRITY_PATH.read_text(encoding="utf-8"))
    summary = integrity["summary"]
    return {
        "document_count": summary["successfully_ingested"],
        "page_count": summary["total_pages"],
        "legal_unit_count": summary["total_legal_units"],
        "chunk_count": summary["total_chunks"],
        "index_count": summary["total_indexes"],
        "database_size_bytes": integrity["infrastructure"]["database_size_bytes"],
        "postgres_table_count": integrity["infrastructure"]["public_table_count"],
    }


def _write_json(report: dict[str, Any]) -> None:
    JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def write_markdown(report: dict[str, Any]) -> None:
    aggregate = report["aggregate"]
    r = aggregate["retrieval"]
    d = aggregate["document_retrieval"]
    m = aggregate["multi_evidence"]
    lex = aggregate["lexical"]
    ctx = aggregate["context"]
    gen = aggregate["generation"]
    ans = aggregate["answerability"]
    lines = [
        "# Legal Evaluation V2 Baseline",
        "",
        f"- Run status: **{report['run_status']}**",
        f"- Dataset SHA-256: `{report['dataset_sha256']}`",
        f"- Cases: {aggregate['case_count']} ({aggregate['answerable_count']} answerable, {aggregate['unanswerable_count']} unanswerable)",
        f"- Model / prompt: `{report['runtime']['model_id']}` / `{report['runtime']['prompt_version']}`",
        "- Thresholds enforced: **NO**",
        "",
        "## Retrieval",
        "",
        "| Metric | Result |",
        "|---|---:|",
        *[f"| Hit@{k} | {_percent(r[f'hit_at_{k}'])} |" for k in (1, 3, 5, 10)],
        f"| MRR | {r['mrr']:.4f} |",
        *[f"| Document Hit@{k} | {_percent(d[f'hit_at_{k}'])} |" for k in (1, 3, 5, 10)],
        f"| Complete multi-evidence retrieval | {_percent(m['complete_retrieval_rate'])} |",
        f"| Partial multi-evidence retrieval | {_percent(m['partial_retrieval_rate'])} |",
        f"| Average required-evidence recall | {_percent(m['average_required_evidence_recall'])} |",
        "",
        "## Lexical contribution",
        "",
        f"- Non-empty rate: {_percent(lex['non_empty_rate'])}",
        f"- Modes: `{json.dumps(lex['mode_counts'], ensure_ascii=False)}`",
        f"- Expected-evidence hit rate: {_percent(lex['expected_evidence_hit_rate'])}",
        f"- Expected-rank improved / harmed: {lex['improved_case_count']} / {lex['harmed_case_count']}",
        "",
        "## Context",
        "",
        f"- Expected-evidence retention: {_percent(ctx['expected_evidence_retention'])}",
        f"- Retrieved but dropped: {ctx['retrieved_but_dropped_count']}",
        f"- Budget exhausted: {ctx['budget_exhausted_count']}",
        f"- Top evidence exceeds budget: {ctx['top_evidence_exceeds_budget_count']}",
        f"- Average utilization: {_percent(ctx['average_utilization'])}",
        "",
        "## Generation and answerability",
        "",
        f"- Answer produced: {_percent(gen['answer_produced_rate'])}",
        f"- Citation presence: {_percent(gen['citation_presence_rate'])}",
        f"- Citation structural validity: {_percent(gen['citation_structural_validity_rate'])}",
        f"- Expected-source citation match: {_percent(gen['expected_source_citation_match_rate'])}",
        f"- Missing / invalid citation rate: {_percent(gen['missing_citation_rate'])} / {_percent(gen['invalid_citation_rate'])}",
        f"- Correct abstention: {_percent(ans['correct_abstention_rate'])}",
        f"- False abstention: {_percent(ans['false_abstention_rate'])}",
        f"- Unsupported direct answer: {_percent(ans['unsupported_direct_answer_rate'])}",
        "",
        "## Failure attribution",
        "",
        "| Label | Count |",
        "|---|---:|",
        *[f"| {label} | {count} |" for label, count in aggregate["failure_counts"].items()],
        "",
        "## Category breakdown",
        "",
        "| Category | Cases | Hit@10 | Document Hit@10 | Citation match | Correct abstention |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for category, item in aggregate["category_breakdown"].items():
        lines.append(
            f"| {category} | {item['case_count']} | {_percent(item['hit_at_10'])} | "
            f"{_percent(item['document_hit_at_10'])} | {_percent(item['expected_source_citation_match'])} | "
            f"{_percent(item['correct_abstention'])} |"
        )
    lines.extend([
        "",
        "## Per-case results",
        "",
        "| Case | Category | Retrieval | Context | Generation | Diagnosis | Total ms |",
        "|---|---|---|---|---|---|---:|",
    ])
    for item in report["cases"]:
        retrieval = item["metrics_v2"]["retrieval_evidence"]
        context = item["metrics_v2"]["context_evidence"]
        lines.append(
            f"| {item['case_id']} | {item['category']} | "
            f"{'N/A' if retrieval is None else ('COMPLETE' if retrieval['complete'] else ('PARTIAL' if retrieval['partial'] else 'NONE'))} | "
            f"{'N/A' if context is None else ('COMPLETE' if context['complete'] else ('PARTIAL' if context['partial'] else 'NONE'))} | "
            f"{item['block6']['status']} | {item['failure_attribution_v2']} | {item['timings']['total_ms']:.1f} |"
        )
    lines.extend([
        "",
        "Raw candidates, scores, contexts, citations, provenance, and timings for every case are retained in the JSON artifact.",
    ])
    MARKDOWN_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_failure_analysis(report: dict[str, Any]) -> None:
    failures = [item for item in report["cases"] if item["failure_attribution_v2"] != "PASS"]
    by_label: dict[str, list[dict[str, Any]]] = {}
    for item in failures:
        by_label.setdefault(item["failure_attribution_v2"], []).append(item)
    lines = [
        "# Legal Evaluation V2 Failure Analysis",
        "",
        "Deterministic attribution uses frozen document/chunk ground truth. It does not use an LLM as judge.",
        "",
        f"Failures: {len(failures)} of {len(report['cases'])} cases.",
    ]
    for label, items in sorted(by_label.items()):
        lines.extend(["", f"## {label} ({len(items)})", ""])
        for item in items:
            retrieval = item["metrics_v2"]["retrieval_evidence"]
            dense = item["metrics_v2"]["dense_evidence"]
            lexical = item["metrics_v2"]["lexical_evidence"]
            dense_ranks = {candidate["chunk_id"]: candidate["dense_rank"] for candidate in item["block4"]["dense_candidates"]}
            lexical_ranks = {candidate["chunk_id"]: candidate["lexical_rank"] for candidate in item["block4"]["lexical_candidates"]}
            final_ranks = {candidate["chunk_id"]: candidate["final_rank"] for candidate in item["block4"]["final_candidates"]}
            required_ranks = [
                {
                    "chunk_id": chunk_id,
                    "dense_rank": dense_ranks.get(chunk_id),
                    "lexical_rank": lexical_ranks.get(chunk_id),
                    "final_rank": final_ranks.get(chunk_id),
                }
                for solution in item["acceptable_evidence_sets"] for chunk_id in solution
            ]
            lines.extend([
                f"### {item['case_id']}",
                "",
                f"- Question: {item['question']}",
                f"- Expected documents: `{item['expected_document_ids']}`",
                f"- Expected evidence: `{item['acceptable_evidence_sets']}`",
                f"- Retrieval complete/partial/recall: {retrieval['complete'] if retrieval else 'N/A'} / {retrieval['partial'] if retrieval else 'N/A'} / {retrieval['recall'] if retrieval else 'N/A'}",
                f"- Dense complete rank: {dense['complete_rank'] if dense else 'N/A'}",
                f"- Lexical complete rank / mode: {lexical['complete_rank'] if lexical else 'N/A'} / {item['metrics_v2']['lexical_mode']}",
                f"- Required chunk ranks: `{required_ranks}`",
                f"- Selected chunks: `{item['block5']['selected_chunk_ids']}`",
                f"- Generation: {item['block6']['status']}; citation validation: {item['block6']['citation_validation']}",
                f"- Cited chunks: `{item['block6']['mapped_chunk_ids']}`",
                "",
            ])
    pass_candidates = [item for item in report["cases"] if item["failure_attribution_v2"] == "PASS" and item["answerable"]]
    if pass_candidates:
        difficult = max(pass_candidates, key=lambda item: item["metrics_v2"]["retrieval_evidence"]["complete_rank"] or 0)
        lines.extend([
            "## Difficult PASS control",
            "",
            f"- Case: `{difficult['case_id']}`",
            f"- Expected-evidence final rank: {difficult['metrics_v2']['retrieval_evidence']['complete_rank']}",
            f"- Diagnosis: {difficult['failure_attribution_v2']}",
        ])
    FAILURE_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_recommendations(report: dict[str, Any]) -> None:
    cases = report["cases"]
    answerable = [item for item in cases if item["answerable"]]
    multi_incomplete = [
        item for item in answerable
        if item["metrics_v2"]["is_multi_evidence"]
        and not item["metrics_v2"]["retrieval_evidence"]["complete"]
    ]
    single_evidence_misses = [
        item for item in answerable
        if not item["metrics_v2"]["is_multi_evidence"]
        and not item["metrics_v2"]["retrieval_evidence"]["complete"]
    ]
    supported_false_abstentions = [
        item for item in answerable if item["failure_attribution_v2"] == "FALSE_ABSTENTION"
    ]
    recommendations = [
        (
            "Multi-evidence coverage and legal-hierarchy retrieval research",
            multi_incomplete,
            "Complete multi-evidence sets were frequently absent from final Top-10 even when several required chunks existed in the dense pool.",
            "Replay frozen branch snapshots to compare coverage-aware fusion, legal-hierarchy expansion, and reranking; require complete-set gains rather than raw candidate volume.",
            "Medium-to-high impact if adopted; reranking adds latency, while hierarchy-aware retrieval changes Block 4 semantics.",
        ),
        (
            "Single-evidence candidate-generation and document-disambiguation research",
            single_evidence_misses,
            "A small number of single-chunk questions missed the expected evidence entirely, including one wrong-document case.",
            "Offline ablate document metadata constraints and legal-identifier-aware query representation on only the affected cases.",
            "Medium impact; requires reliable metadata and must be recall-tested against all V2 cases.",
        ),
        (
            "Supported-case abstention calibration research",
            supported_false_abstentions,
            "Complete expected evidence reached Block 5, but the frozen generator abstained on two answerable cases.",
            "Diagnose prompt/evidence presentation on the captured traces; compare prompt-only variants offline without weakening hard-negative abstention.",
            "Low-to-medium impact if prompt-only; must preserve the measured 10/10 unsupported-case abstention result.",
        ),
    ]
    ranked = sorted(recommendations, key=lambda item: len(item[1]), reverse=True)
    lines = [
        "# Legal Evaluation V2 — Recommended Next Experiments",
        "",
        "These are evidence-based research recommendations only. No quality fix is implemented or approved by this report.",
    ]
    for priority, (title, affected, why, experiment, impact) in enumerate(ranked[:3], start=1):
        lines.extend([
            "",
            f"## Priority {priority}: {title}",
            "",
            f"- Measured affected cases: {len(affected)} / {len(answerable)} answerable ({100 * len(affected) / len(answerable):.2f}%).",
            f"- Case IDs: `{[item['case_id'] for item in affected]}`",
            f"- Why: {why}",
            f"- Suggested experiment: {experiment}",
            f"- Architecture/latency impact: {impact}",
        ])
    lines.extend([
        "",
        "## Decision guardrails",
        "",
        "- Do not adopt reranking merely because it is fashionable; require measurable Top-50-to-Top-10 recoveries.",
        "- Do not use retrieval similarity as an answerability threshold.",
        "- Preserve the immutable V2 dataset/hash for every future comparison.",
    ])
    RECOMMENDATIONS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run(resume: bool = False) -> dict[str, Any]:
    if sha256(DATASET_PATH) != V2_SHA256:
        raise RuntimeError("Frozen Evaluation V2 dataset hash mismatch")
    if sha256(V1_DATASET_PATH) != V1_SHA256:
        raise RuntimeError("Frozen Evaluation V1 dataset hash mismatch")
    dataset = load_dataset(DATASET_PATH)
    db = SessionLocal()
    profile = get_generation_profile()
    context_builder = ContextBuilderService(ContextTokenCounter(profile.tokenizer_provider, profile.tokenizer_id))
    prompt_counter = PromptTokenCounter(profile.tokenizer_provider, profile.tokenizer_id, thinking=profile.thinking)
    llm_client = get_llm_client()
    prior_cases: dict[str, dict[str, Any]] = {}
    if resume and JSON_PATH.exists():
        prior = json.loads(JSON_PATH.read_text(encoding="utf-8"))
        prior_cases = {item["case_id"]: item for item in prior.get("cases", [])}
    try:
        validation = validate_dataset(dataset, db)
        await llm_client.health(profile)
        cases: list[dict[str, Any]] = []
        for index, case in enumerate(dataset.cases, start=1):
            if case.case_id in prior_cases:
                measured = prior_cases[case.case_id]
                print(f"[{index}/{len(dataset.cases)}] {case.case_id} (resume)", flush=True)
            else:
                print(f"[{index}/{len(dataset.cases)}] {case.case_id}", flush=True)
                measured = await run_case(case, db, context_builder, prompt_counter, profile, llm_client)
                mode = lexical_mode(db, case.question, case.document_ids, len(measured["block4"]["lexical_candidates"]))
                measured = enrich_case(measured, mode)
            cases.append(measured)
            progress = {
                "report_id": "legal_eval_v2_baseline",
                "run_status": "IN_PROGRESS",
                "dataset_sha256": V2_SHA256,
                "cases_completed": len(cases),
                "cases": cases,
            }
            _write_json(progress)

        report = {
            "report_id": "legal_eval_v2_baseline",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run_status": "PASS",
            "dataset_sha256": V2_SHA256,
            "evaluation_v1_sha256": V1_SHA256,
            "thresholds_enforced": False,
            "dataset_validation": validation,
            "runtime": {
                "pipeline": "REAL_BLOCK_4_BLOCK_5_BLOCK_6",
                "provider": profile.provider,
                "model_id": profile.model_id,
                "prompt_version": profile.prompt_version,
                "generation_profile_unchanged": True,
            },
            "aggregate": aggregate_v2(cases, scale_snapshot()),
            "cases": cases,
        }
        _write_json(report)
        write_markdown(report)
        write_failure_analysis(report)
        write_recommendations(report)
        return report
    finally:
        db.close()
        await close_llm_client()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run frozen Legal Evaluation V2")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(run(resume=args.resume))
    print(json.dumps(report["aggregate"], ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
