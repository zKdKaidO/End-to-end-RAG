import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from structlog.contextvars import bind_contextvars, clear_contextvars

from app.context.schemas import StopReason
from app.context.service import ContextBuilderService
from app.db.database import SessionLocal
from app.generation.citations import validate_and_map_citations
from app.generation.answerability import parse_answerability
from app.generation.profile import get_generation_profile
from app.generation.prompting import assemble_messages
from app.generation.runtime import close_llm_client, get_llm_client
from app.generation.schemas import (
    AnswerabilityStatus,
    AnswerabilityValidation,
    CitationValidation,
    GenerationStatus,
)
from app.generation.tokenizers import ContextTokenCounter, PromptTokenCounter
from app.orchestration.answer_service import INSUFFICIENT_EVIDENCE_MESSAGE
from app.retrieval.query_embedder import QueryEmbedder
from app.retrieval.repository import RetrievalRepository
from app.retrieval.schemas import RetrievalRequest
from app.retrieval.service import RetrievalService, validate_request
from evaluation.context_metrics import context_retention
from evaluation.dataset_validator import load_dataset, validate_dataset
from evaluation.gate import aggregate_reports
from evaluation.generation_metrics import classify_failure, expected_source_match, unsupported_answer
from evaluation.reports import write_markdown
from evaluation.retrieval_metrics import acceptable_solution_rank, hit_at_k, reciprocal_rank


class CapturingEmbedder:
    def __init__(self, delegate):
        self.delegate = delegate
        self.elapsed_ms = 0.0

    def encode(self, query_text):
        started = perf_counter()
        value = self.delegate.encode(query_text)
        self.elapsed_ms = (perf_counter() - started) * 1000
        return value


class CapturingRepository:
    def __init__(self, delegate):
        self.delegate = delegate
        self.dense = []
        self.lexical = []
        self.timings = {}

    def dense_search(self, *args):
        started = perf_counter()
        self.dense = self.delegate.dense_search(*args)
        self.timings["dense_search_ms"] = (perf_counter() - started) * 1000
        return self.dense

    def lexical_search(self, *args):
        started = perf_counter()
        self.lexical = self.delegate.lexical_search(*args)
        self.timings["lexical_search_ms"] = (perf_counter() - started) * 1000
        return self.lexical

    def hydrate(self, *args):
        started = perf_counter()
        value = self.delegate.hydrate(*args)
        self.timings["hydration_ms"] = (perf_counter() - started) * 1000
        return value


def _candidate(candidate, branch):
    data = asdict(candidate)
    data["chunk_id"] = str(data["chunk_id"])
    data["document_id"] = str(data["document_id"])
    return data


async def run_case(case, db, context_builder, prompt_counter, profile, llm_client):
    case_started = perf_counter()
    request_id = f"eval-{case.case_id}"
    clear_contextvars()
    bind_contextvars(request_id=request_id)

    capture_embedder = CapturingEmbedder(QueryEmbedder.get_instance())
    capture_repo = CapturingRepository(RetrievalRepository(db))
    retrieval_service = RetrievalService(db, embedder=capture_embedder, repository=capture_repo)
    params = validate_request(
        RetrievalRequest(query_text=case.question, document_ids=case.document_ids)
    )
    retrieval_started = perf_counter()
    retrieved = retrieval_service.retrieve(params)
    retrieval_ms = (perf_counter() - retrieval_started) * 1000

    final_chunk_ids = [item["chunk_id"] for item in retrieved]
    context_started = perf_counter()
    package = context_builder.build(
        request_id=request_id,
        query_text=case.question,
        retrieved_candidates=retrieved,
        context_budget_tokens=profile.context_budget_tokens,
    )
    context_ms = (perf_counter() - context_started) * 1000
    selected_chunk_ids = [item.chunk_id for item in package.selected_evidence]
    retrieved_found, retained, dropped = context_retention(
        final_chunk_ids, selected_chunk_ids, case.acceptable_evidence_sets
    ) if case.answerable else (False, False, False)

    prompt_tokens = 0
    provider_called = False
    ttft_ms = None
    generation_ms = 0.0
    if package.selected_count == 0:
        status = GenerationStatus.INSUFFICIENT_EVIDENCE
        answer_text = INSUFFICIENT_EVIDENCE_MESSAGE
        citations, invalid_citations = [], []
        citation_validation = CitationValidation.PASS
        finish_reason = None
        usage = None
        answerability_status = AnswerabilityStatus.INSUFFICIENT_EVIDENCE
        answerability_validation = AnswerabilityValidation.NOT_APPLICABLE
    else:
        messages = assemble_messages(package, profile.prompt_version)
        prompt_tokens = prompt_counter.count_messages(messages)
        if prompt_tokens + profile.max_output_tokens + profile.prompt_token_safety_margin > profile.model_context_limit:
            raise RuntimeError(f"{case.case_id}: final prompt exceeds model context limit")
        provider_called = True
        pieces = []
        finish_reason = None
        usage = None
        generation_started = perf_counter()
        async for chunk in llm_client.stream(messages, profile):
            if chunk.text:
                if ttft_ms is None:
                    ttft_ms = (perf_counter() - generation_started) * 1000
                pieces.append(chunk.text)
            if chunk.done:
                finish_reason = chunk.finish_reason
                usage = chunk.usage
        generation_ms = (perf_counter() - generation_started) * 1000
        provider_text = "".join(pieces)
        parsed = parse_answerability(provider_text)
        answerability_status = parsed.status
        answerability_validation = parsed.validation
        if parsed.status == AnswerabilityStatus.INSUFFICIENT_EVIDENCE:
            answer_text = INSUFFICIENT_EVIDENCE_MESSAGE
            citations, invalid_citations = [], []
            citation_validation = CitationValidation.PASS
            status = GenerationStatus.INSUFFICIENT_EVIDENCE
        else:
            answer_text = parsed.public_text
            citations, invalid_citations, citation_validation, status = validate_and_map_citations(
                answer_text, package.selected_evidence
            )
            if parsed.validation != AnswerabilityValidation.PASS:
                status = GenerationStatus.COMPLETED_WITH_WARNINGS

    mapped_chunk_ids = [citation.chunk_id for citation in citations]
    mapped_document_ids = [citation.document_id for citation in citations]
    source_match = (
        expected_source_match(mapped_chunk_ids, case.acceptable_evidence_sets)
        if case.answerable
        else None
    )
    solution_rank = (
        acceptable_solution_rank(final_chunk_ids, case.acceptable_evidence_sets)
        if case.answerable
        else None
    )
    failure = classify_failure(
        answerable=case.answerable,
        retrieval_found=retrieved_found,
        context_retained=retained,
        status=status.value,
        answer_text=answer_text,
        citation_validation=citation_validation.value,
        expected_citation_match=source_match,
    )
    total_ms = (perf_counter() - case_started) * 1000
    return {
        "case_id": case.case_id,
        "category": case.category.value,
        "question": case.question,
        "answerable": case.answerable,
        "document_ids": case.document_ids,
        "expected_document_ids": case.expected_document_ids,
        "acceptable_evidence_sets": case.acceptable_evidence_sets,
        "source_reference": case.source_reference,
        "notes": case.notes,
        "block4": {
            "dense_candidates": [_candidate(item, "dense") for item in capture_repo.dense],
            "lexical_candidates": [_candidate(item, "lexical") for item in capture_repo.lexical],
            "rrf_candidates": [
                item.model_dump(mode="json")
                for item in retrieval_service.last_base_candidates
            ],
            "hierarchy_candidates": [
                item for item in retrieved if item["candidate_origin"] == "HIERARCHY_CHILD"
            ],
            "hierarchy_diagnostics": (
                retrieval_service.last_hierarchy_diagnostics.as_dict()
            ),
            "final_candidates": retrieved,
            "query_embedding_ms": capture_embedder.elapsed_ms,
            **capture_repo.timings,
        },
        "block5": {
            "candidate_count": package.candidate_count,
            "duplicates_removed": package.duplicate_count,
            "selected_source_ids": [item.source_id for item in package.selected_evidence],
            "selected_chunk_ids": selected_chunk_ids,
            "selected_retrieval_ranks": [item.retrieval_final_rank for item in package.selected_evidence],
            "selected_context_orders": [item.context_candidate_order for item in package.selected_evidence],
            "selected_candidate_origins": [item.candidate_origin.value for item in package.selected_evidence],
            "context_token_count": package.context_token_count,
            "context_budget_tokens": package.context_budget_tokens,
            "budget_exhausted": package.budget_exhausted,
            "stop_reason": package.stop_reason.value,
        },
        "block6": {
            "status": status.value,
            "answer_text": answer_text,
            "used_source_ids": [citation.source_id for citation in citations],
            "citations": [citation.model_dump(mode="json") for citation in citations],
            "invalid_citations": invalid_citations,
            "citation_validation": citation_validation.value,
            "mapped_chunk_ids": mapped_chunk_ids,
            "mapped_document_ids": mapped_document_ids,
            "provider_called": provider_called,
            "provider_usage": usage.model_dump(mode="json") if usage else None,
            "finish_reason": finish_reason,
            "prompt_tokens": prompt_tokens,
            "model_id": profile.model_id,
            "prompt_version": profile.prompt_version,
            "answerability_status": answerability_status.value if answerability_status else None,
            "answerability_validation": answerability_validation.value,
        },
        "metrics": {
            "hit_at_1": bool(hit_at_k(final_chunk_ids, case.acceptable_evidence_sets, 1)) if case.answerable else None,
            "hit_at_3": bool(hit_at_k(final_chunk_ids, case.acceptable_evidence_sets, 3)) if case.answerable else None,
            "hit_at_5": bool(hit_at_k(final_chunk_ids, case.acceptable_evidence_sets, 5)) if case.answerable else None,
            "hit_at_10": bool(hit_at_k(final_chunk_ids, case.acceptable_evidence_sets, 10)) if case.answerable else None,
            "reciprocal_rank": reciprocal_rank(final_chunk_ids, case.acceptable_evidence_sets) if case.answerable else None,
            "expected_evidence_rank": solution_rank,
            "retrieval_found": retrieved_found if case.answerable else None,
            "context_retained": retained if case.answerable else None,
            "retrieved_but_dropped": dropped if case.answerable else None,
            "expected_source_match": source_match,
            "unsupported_answer": unsupported_answer(case.answerable, status.value, answer_text),
        },
        "failure_attribution": failure.value if failure else None,
        "timings": {
            "retrieval_ms": retrieval_ms,
            "context_ms": context_ms,
            "ttft_ms": ttft_ms,
            "generation_ms": generation_ms,
            "total_ms": total_ms,
        },
    }


async def run(dataset_path: Path, json_path: Path, markdown_path: Path):
    dataset = load_dataset(dataset_path)
    db = SessionLocal()
    profile = get_generation_profile()
    context_builder = ContextBuilderService(
        ContextTokenCounter(profile.tokenizer_provider, profile.tokenizer_id)
    )
    prompt_counter = PromptTokenCounter(
        profile.tokenizer_provider, profile.tokenizer_id, thinking=profile.thinking
    )
    llm_client = get_llm_client()
    try:
        validation = validate_dataset(dataset, db)
        await llm_client.health(profile)
        cases = []
        for index, case in enumerate(dataset.cases, start=1):
            print(f"[{index}/{len(dataset.cases)}] {case.case_id}", flush=True)
            cases.append(
                await run_case(case, db, context_builder, prompt_counter, profile, llm_client)
            )
        report = {
            "report_id": dataset.dataset_id,
            "dataset_version": dataset.version,
            "thresholds_enforced": False,
            "dataset_validation": validation,
            "aggregate": aggregate_reports(cases),
            "cases": cases,
        }
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        write_markdown(markdown_path, report)
        return report
    finally:
        db.close()
        await close_llm_client()


def main():
    parser = argparse.ArgumentParser(description="Run the offline Legal RAG Evaluation Gate V1")
    parser.add_argument("--dataset", type=Path, default=Path("evaluation/datasets/legal_eval_v1.json"))
    parser.add_argument("--json-report", type=Path, default=Path("evaluation/reports/legal_eval_v1.json"))
    parser.add_argument("--markdown-report", type=Path, default=Path("evaluation/reports/legal_eval_v1.md"))
    args = parser.parse_args()
    report = asyncio.run(run(args.dataset, args.json_report, args.markdown_report))
    print(json.dumps(report["aggregate"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
