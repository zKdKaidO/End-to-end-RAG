"""Real targeted regressions for the narrowly amended Block 4/6 contracts."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from app.context.service import ContextBuilderService
from app.db.database import SessionLocal
from app.generation.profile import get_generation_profile
from app.generation.prompting import assemble_messages
from app.generation.runtime import close_llm_client, get_llm_client
from app.generation.schemas import AnswerRequest
from app.generation.tokenizers import ContextTokenCounter, PromptTokenCounter
from app.orchestration.answer_service import AnswerService
from app.retrieval.query_embedder import QueryEmbedder
from app.retrieval.repository import RetrievalRepository
from app.retrieval.service import RetrievalService
from evaluation.dataset_validator import load_dataset
from evaluation.runner import CapturingEmbedder, CapturingRepository


DATASET = Path("evaluation/datasets/legal_eval_v1.json")
OUTPUT = Path("evaluation/reports/quality_fix_targeted_v1.json")
EXPECTED_HASH = "afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245"


def _hash() -> str:
    return hashlib.sha256(DATASET.read_bytes()).hexdigest()


def _branch_candidate(item) -> dict:
    value = asdict(item)
    value["chunk_id"] = str(value["chunk_id"])
    value["document_id"] = str(value["document_id"])
    return value


def _selected(item) -> dict:
    return item.model_dump(mode="json")


async def _prepare(case, db, llm, profile, builder, counter):
    embedder = CapturingEmbedder(QueryEmbedder.get_instance())
    repository = CapturingRepository(RetrievalRepository(db))
    service = AnswerService(
        RetrievalService(db, embedder=embedder, repository=repository),
        llm,
        profile,
        context_builder=builder,
        prompt_counter=counter,
    )
    prepared = await service.prepare(
        f"quality-fix-{case.case_id}",
        AnswerRequest(query_text=case.question, document_ids=case.document_ids),
    )
    return service, prepared, repository, embedder


async def _run_generation(case, db, llm, profile, builder, counter, run_number):
    service, prepared, repository, embedder = await _prepare(
        case, db, llm, profile, builder, counter
    )
    started = perf_counter()
    result = await service.answer_prepared(prepared)
    latency_ms = (perf_counter() - started) * 1000
    if "[STATUS:" in result.answer_text:
        raise RuntimeError(f"Internal marker leaked for {case.case_id}")
    return {
        "run": run_number,
        "question": case.question,
        "dense_candidates": [_branch_candidate(item) for item in repository.dense],
        "lexical_candidates": [_branch_candidate(item) for item in repository.lexical],
        "selected_evidence": [_selected(item) for item in prepared.package.selected_evidence],
        "context_text": prepared.package.context_text,
        "context_token_count": prepared.package.context_token_count,
        "prompt_tokens": prepared.prompt_tokens,
        "answerability_status": result.answerability_status.value if result.answerability_status else None,
        "answerability_validation": result.answerability_validation.value,
        "public_status": result.status.value,
        "answer_text": result.answer_text,
        "citations": [item.model_dump(mode="json") for item in result.citations],
        "invalid_citations": result.invalid_citations,
        "citation_validation": result.citation_validation.value,
        "provider_called": prepared.early_result is None,
        "finish_reason": result.finish_reason,
        "usage": result.usage.model_dump(mode="json") if result.usage else None,
        "generation_latency_ms": latency_ms,
        "query_embedding_ms": embedder.elapsed_ms,
        "repository_timings": repository.timings,
    }


async def run() -> dict:
    dataset_hash = _hash()
    if dataset_hash != EXPECTED_HASH:
        raise RuntimeError("Frozen evaluation dataset hash mismatch")
    dataset = load_dataset(DATASET)
    cases = {case.case_id: case for case in dataset.cases}
    profile = get_generation_profile()
    builder = ContextBuilderService(
        ContextTokenCounter(profile.tokenizer_provider, profile.tokenizer_id)
    )
    counter = PromptTokenCounter(
        profile.tokenizer_provider, profile.tokenizer_id, thinking=profile.thinking
    )
    llm = get_llm_client()
    db = SessionLocal()
    try:
        await llm.health(profile)
        unanswerable = {}
        for case in [item for item in dataset.cases if not item.answerable]:
            print(f"unanswerable {case.case_id}", flush=True)
            unanswerable[case.case_id] = await _run_generation(
                case, db, llm, profile, builder, counter, 1
            )

        citation_stability = {}
        for case_id in ("nsmo_definition", "domestic_expert_pay_cap"):
            citation_stability[case_id] = []
            for run_number in range(1, 4):
                print(f"citation {case_id} run {run_number}", flush=True)
                citation_stability[case_id].append(
                    await _run_generation(
                        cases[case_id], db, llm, profile, builder, counter, run_number
                    )
                )

        multi_evidence = {}
        for case_id in ("applicable_entities_multi", "national_dispatcher_role"):
            case = cases[case_id]
            _, prepared, repository, _ = await _prepare(
                case, db, llm, profile, builder, counter
            )
            dense = {str(item.chunk_id): item.dense_rank for item in repository.dense}
            lexical = {str(item.chunk_id): item.lexical_rank for item in repository.lexical}
            final = {
                item.chunk_id: item.retrieval_final_rank
                for item in prepared.package.selected_evidence
            }
            required = []
            for chunk_id in case.acceptable_evidence_sets[0]:
                required.append({
                    "chunk_id": chunk_id,
                    "dense_rank": dense.get(chunk_id),
                    "lexical_rank": lexical.get(chunk_id),
                    "final_rank": final.get(chunk_id),
                })
            multi_evidence[case_id] = {
                "question": case.question,
                "required_evidence": required,
                "lexical_candidate_count": len(repository.lexical),
                "final_top_10": [
                    {"source_id": item.source_id, "chunk_id": item.chunk_id, "final_rank": item.retrieval_final_rank}
                    for item in prepared.package.selected_evidence
                ],
            }

        wrong_source = await _run_generation(
            cases["oda_capital_source"], db, llm, profile, builder, counter, 1
        )

        sample_service, sample_prepared, _, _ = await _prepare(
            cases["nsmo_definition"], db, llm, profile, builder, counter
        )
        v1_tokens = counter.count_messages(
            assemble_messages(sample_prepared.package, "legal-rag-v1")
        )
        v2_tokens = counter.count_messages(
            assemble_messages(sample_prepared.package, "legal-rag-v2")
        )
        report = {
            "report_id": "quality_fix_targeted_v1",
            "dataset_sha256": dataset_hash,
            "profile": profile.__dict__,
            "prompt_measurement": {
                "legal_rag_v1_tokens": v1_tokens,
                "legal_rag_v2_tokens": v2_tokens,
                "overhead_tokens": v2_tokens - v1_tokens,
                "budget_total": v2_tokens + profile.max_output_tokens + profile.prompt_token_safety_margin,
                "model_context_limit": profile.model_context_limit,
                "budget_guard_pass": v2_tokens + profile.max_output_tokens + profile.prompt_token_safety_margin <= profile.model_context_limit,
                "tokenizer_shared_instance": builder.token_counter._tokenizer is counter._tokenizer,
                "context_vi_token_count": builder.token_counter.count("Việt Nam"),
            },
            "unanswerable": unanswerable,
            "citation_stability": citation_stability,
            "multi_evidence": multi_evidence,
            "wrong_source": wrong_source,
            "wrong_source_classification": "PLAUSIBLE_ALTERNATIVE_EVIDENCE",
            "production_answer_service_class": type(sample_service).__name__,
        }
        if _hash() != EXPECTED_HASH:
            raise RuntimeError("Frozen evaluation dataset changed during targeted run")
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({
            "prompt_measurement": report["prompt_measurement"],
            "unanswerable": {key: {"answerability": value["answerability_status"], "status": value["public_status"], "citations": len(value["citations"])} for key, value in unanswerable.items()},
            "citation_stability": {key: [{"status": run["public_status"], "answerability": run["answerability_status"], "citation_validation": run["citation_validation"], "citations": [item["source_id"] for item in run["citations"]]} for run in runs] for key, runs in citation_stability.items()},
            "multi_evidence": multi_evidence,
            "wrong_source_citations": [item["chunk_id"] for item in wrong_source["citations"]],
        }, ensure_ascii=False, indent=2))
        return report
    finally:
        db.close()
        await close_llm_client()


if __name__ == "__main__":
    asyncio.run(run())
