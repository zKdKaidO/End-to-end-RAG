"""Developer-only local RAG quality harness.

Reports stable identifiers, ranks, coverage signals, result metadata, and
timings. It never writes source document text. Output must be directed outside
the repository when production-local documents are evaluated.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from time import perf_counter

from app.context.service import ContextBuilderService
from app.generation.tokenizers import ContextTokenCounter
from app.local_compute.answer_modes import AnswerMode, answer_mode_profile
from app.local_compute.catalog import LocalCatalog
from app.local_compute.context_adapter import build_local_context
from app.local_compute.generation import (
    GenerationRoutingRequest,
    LocalAnswerService,
)
from app.local_compute.production_launcher import build_settings
from app.local_compute.runtime import LocalComputeRuntime
from app.local_compute.retrieval import LocalRetrievalStore
from app.local_compute.hierarchy import LocalHierarchyRepository
try:  # The harness can also measure a detached pre-QueryPlan baseline.
    from app.local_compute.query_plan import plan_query
except ImportError:  # pragma: no cover - exercised only against frozen baseline
    plan_query = None


CASES = {
    "regression-a": (
        "Tôi không tham gia khóa đào tạo nào nhưng muốn tích lũy giờ cập nhật "
        "kiến thức công tác xã hội bằng các hoạt động học thuật. Nếu tôi là tác "
        "giả liên hệ của 1 bài báo khoa học quốc tế và đồng hướng dẫn 1 luận án "
        "tiến sĩ đã được thông qua thì tôi được tính tổng cộng bao nhiêu giờ tín "
        "chỉ? Hai hoạt động này thuộc những hình thức cập nhật kiến thức nào?"
    ),
    "regression-b": (
        "Theo tài liệu, người hành nghề công tác xã hội có thể cập nhật kiến "
        "thức bằng hoạt động nghiên cứu khoa học và bằng hướng dẫn luận văn/luận "
        "án như thế nào? Hãy nêu các hoạt động tương ứng và cho biết chúng thuộc "
        "hai hình thức cập nhật kiến thức nào."
    ),
    "direct-control": "Các hình thức cập nhật kiến thức công tác xã hội là gì?",
}


def _candidate_summary(item: dict) -> dict:
    return {
        "chunk_id": item["chunk_id"],
        "document_id": item["document_id"],
        "candidate_origin": item["candidate_origin"],
        "retrieval_final_rank": item.get("retrieval_final_rank"),
        "dense_rank": item.get("dense_rank"),
        "lexical_rank": item.get("lexical_rank"),
        "fusion_score": item.get("fusion_score"),
        "hierarchy_relation": item.get("hierarchy_relation"),
        "anchor_chunk_id": item.get("anchor_chunk_id"),
    }


async def _run_case(settings, case_id: str, query: str, mode: AnswerMode, *, preview: bool) -> dict:
    runtime = LocalComputeRuntime(settings)
    router = runtime.generation_router()
    profile = router.local_provider.profile
    retrieval = LocalAnswerService(
        settings, LocalCatalog(settings.catalog_path), router, profile=profile
    ).retrieval_store
    started = perf_counter()
    retrieval_started = perf_counter()
    plan = plan_query(query) if plan_query is not None else None
    retrieval_args = (query, None, mode)
    if plan is not None and len(plan.retrieval_queries) > 1:
        retrieval_args = (*retrieval_args, plan.retrieval_queries)
    results, hierarchy = retrieval.query_document_set_with_diagnostics(*retrieval_args)
    retrieval_ms = (perf_counter() - retrieval_started) * 1000
    context_started = perf_counter()
    package = build_local_context(
        request_id=f"quality-{case_id}-{mode.value}",
        query_text=query,
        local_results=results,
        context_budget_tokens=min(profile.context_budget_tokens, answer_mode_profile(mode).context_budget_tokens),
        context_builder=ContextBuilderService(
            ContextTokenCounter(profile.tokenizer_provider, profile.tokenizer_id)
        ),
    )
    context_ms = (perf_counter() - context_started) * 1000
    service = LocalAnswerService(
        settings, LocalCatalog(settings.catalog_path), router, profile=profile
    )
    response = await service.answer(
        request_id=f"quality-{case_id}-{mode.value}",
        query_text=query,
        document_ids=None,
        answer_mode=mode,
        routing=GenerationRoutingRequest(),
    )
    answer = response.result.answer_text
    record = {
        "case_id": case_id,
        "mode": mode.value,
        "query": query,
        "model": response.model_id,
        "retrieved_base_candidates": [
            _candidate_summary(item)
            for item in results
            if item["candidate_origin"] == "RETRIEVAL"
        ],
        "hierarchy_child_ids": [
            item["chunk_id"]
            for item in results
            if item["candidate_origin"] == "HIERARCHY_CHILD"
        ],
        "selected_evidence_ids": [item.source_id for item in package.selected_evidence],
        "selected_chunk_ids": [item.chunk_id for item in package.selected_evidence],
        "context_token_count": package.context_token_count,
        "context_budget_tokens": package.context_budget_tokens,
        "answerability_result": response.result.answerability_status.value if response.result.answerability_status else None,
        "generation_status": response.result.status.value,
        "citation_ids": [item.source_id for item in response.result.citations],
        "answer_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
        "timings": {
            "retrieval_ms": round(retrieval_ms, 3),
            "rerank_ms": None,
            "planning_ms": response.timings.get("planning_ms"),
            "context_ms": round(context_ms, 3),
            "generation_ms": response.timings.get("generation_ms"),
            "total_ms": round((perf_counter() - started) * 1000, 3),
        },
        "hierarchy_diagnostics": hierarchy,
    }
    if preview:
        record["answer_preview"] = answer[:1200]
    await router.local_provider.close()
    return record


async def _main(args) -> list[dict]:
    settings = build_settings()
    if args.structured_text or args.container_local:
        settings = replace(
            settings,
            development_mode=True,
            local_generation_base_url="http://host.docker.internal:11434",
        )
    if args.structured_text:
        # Kept explicitly developer-only: the installed profile remains v2
        # until this source/runtime quality gate has passed.
        settings = replace(
            settings,
            generation_prompt_version="legal-rag-v4-structured",
            generation_structured_output=True,
        )
    if args.structured_text or args.container_local:
        # The harness may be run in an ephemeral Linux container against the
        # Windows-installed artifact catalog. This process-local adapter never
        # changes persisted paths or product behavior.
        original_artifact = LocalRetrievalStore._artifact
        LocalRetrievalStore._artifact = lambda store, artifact_id: original_artifact(store, artifact_id).replace("\\", "/")
        original_artifact_path = LocalHierarchyRepository._artifact_path
        LocalHierarchyRepository._artifact_path = lambda repository, document_id, artifact_id: Path(str(original_artifact_path(repository, document_id, artifact_id)).replace("\\", "/"))
    if args.model:
        tokenizer = "Qwen/Qwen3.5-27B" if args.model.endswith(":27b") else settings.generation_tokenizer_id
        settings = replace(settings, generation_model_id=args.model, generation_tokenizer_id=tokenizer)
    selected = CASES if args.case == "all" else {args.case: CASES[args.case]}
    records = []
    modes = (AnswerMode(args.mode),) if args.mode else tuple(AnswerMode)
    for case_id, query in selected.items():
        for mode in modes:
            records.append(await _run_case(settings, case_id, query, mode, preview=args.include_answer_preview))
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=[*CASES, "all"], default="all")
    parser.add_argument("--model")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=[item.value for item in AnswerMode])
    parser.add_argument("--include-answer-preview", action="store_true")
    parser.add_argument(
        "--structured-text",
        action="store_true",
        help="Developer-only: exercise the v4 structured textual support contract.",
    )
    parser.add_argument(
        "--container-local",
        action="store_true",
        help="Developer-only: adapt a read-only Windows local artifact mount for an ephemeral Linux runner.",
    )
    args = parser.parse_args()
    records = asyncio.run(_main(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"records": len(records), "output": str(args.output)}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
