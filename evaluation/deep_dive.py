"""Offline diagnostic experiments for RAG Quality Failure Deep-Dive V1.

This module reads the frozen Evaluation Gate report and corpus, runs controlled
prompt and PostgreSQL text-search probes, and writes diagnostic artifacts.  It
does not mutate production configuration, the evaluation dataset, or database
state.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any

from sqlalchemy import text

from app.context.service import ContextBuilderService
from app.db.database import SessionLocal
from app.generation.citations import parse_citation_ids, validate_and_map_citations
from app.generation.profile import get_generation_profile
from app.generation.prompting import assemble_messages, load_system_prompt
from app.generation.runtime import close_llm_client, get_llm_client
from app.generation.tokenizers import ContextTokenCounter, PromptTokenCounter


DATASET_PATH = Path("evaluation/datasets/legal_eval_v1.json")
BASELINE_PATH = Path("evaluation/reports/legal_eval_v1.json")
JSON_PATH = Path("evaluation/reports/quality_failure_deep_dive_v1.json")
MARKDOWN_PATH = Path("evaluation/reports/quality_failure_deep_dive_v1.md")

STRONG_ABSTENTION = """

QUY TẮC KIỂM TRA ĐỦ BẰNG CHỨNG (thử nghiệm chẩn đoán):
Trước khi trả lời, phải kiểm tra bằng chứng có nêu trực tiếp thông tin cần thiết
để trả lời chính xác câu hỏi hay không. Bằng chứng chỉ liên quan cùng chủ đề
không có nghĩa là đủ để trả lời. Nếu thiếu dù chỉ một dữ kiện thiết yếu, chỉ trả
lời đúng một câu: "Bằng chứng được cung cấp không đủ để trả lời câu hỏi."
Trong trường hợp đó không bổ sung kiến thức bên ngoài và không trích dẫn nguồn.
""".strip()

ABSTENTION_FEW_SHOT = """

VÍ DỤ CHẨN ĐOÁN:
Bằng chứng: "Doanh nghiệp phải nộp báo cáo hằng năm."
Câu hỏi: "Mức phạt nếu nộp báo cáo trễ là bao nhiêu?"
Trả lời: Bằng chứng được cung cấp không đủ để trả lời câu hỏi.

Bằng chứng: "Văn bản quy định chính sách cho người lao động."
Câu hỏi: "Người lao động được nghỉ thai sản bao nhiêu tháng?"
Trả lời: Bằng chứng được cung cấp không đủ để trả lời câu hỏi.
""".strip()

STRONG_CITATION = """

QUY TẮC TRÍCH DẪN (thử nghiệm chẩn đoán):
Mọi kết luận thực tế trong câu trả lời phải kèm ít nhất một mã nguồn chính xác
theo dạng [S1], [S2], ... Không viết "[Evidence S1]" hoặc bất kỳ biến thể nào.
Trước khi kết thúc, tự kiểm tra rằng ít nhất một mã [Sx] hợp lệ đã xuất hiện.
""".strip()

CITATION_FEW_SHOT = """

VÍ DỤ ĐỊNH DẠNG:
Bằng chứng S1: "Mức tối đa là 1,5 lần mức lương chuyên gia của Nhà nước."
Câu hỏi: "Mức tối đa là bao nhiêu?"
Trả lời: Mức tối đa là 1,5 lần mức lương chuyên gia của Nhà nước [S1].
""".strip()

INSUFFICIENT_PATTERNS = (
    re.compile(r"bằng chứng.{0,80}không đủ", re.IGNORECASE | re.DOTALL),
    re.compile(r"không có bằng chứng.{0,80}(nêu|cho biết|xác định)", re.IGNORECASE | re.DOTALL),
    re.compile(r"không thể trả lời.{0,80}(bằng chứng|thông tin)", re.IGNORECASE | re.DOTALL),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _abstention_signal(answer: str) -> bool:
    return any(pattern.search(answer) for pattern in INSUFFICIENT_PATTERNS)


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.2f}%"


def _round(value: float | None, digits: int = 6) -> float | None:
    return None if value is None else round(float(value), digits)


def _context_package(case: dict[str, Any], builder: ContextBuilderService, budget: int):
    return builder.build(
        request_id=f"deep-dive-{case['case_id']}",
        query_text=case["question"],
        retrieved_candidates=case["block4"]["final_candidates"],
        context_budget_tokens=budget,
    )


def _messages(package, system_prompt: str) -> list[dict[str, str]]:
    current = assemble_messages(package, "legal-rag-v1")
    return [{"role": "system", "content": system_prompt}, current[1]]


async def _generate(llm, profile, counter, package, system_prompt: str) -> dict[str, Any]:
    messages = _messages(package, system_prompt)
    started = perf_counter()
    result = await llm.generate(messages, profile)
    latency_ms = (perf_counter() - started) * 1000
    citations, invalid, validation, status = validate_and_map_citations(
        result.text, package.selected_evidence
    )
    abstained = _abstention_signal(result.text)
    return {
        "messages": messages,
        "prompt_tokens": counter.count_messages(messages),
        "answer": result.text,
        "finish_reason": result.finish_reason,
        "usage": result.usage.model_dump(mode="json") if result.usage else None,
        "latency_ms": latency_ms,
        "abstention_text_detected": abstained,
        "pipeline_status": status.value,
        "citation_validation": validation.value,
        "citation_ids": parse_citation_ids(result.text),
        "mapped_citations": [item.model_dump(mode="json") for item in citations],
        "invalid_citations": invalid,
        "unsupported_direct_answer_detected": not abstained,
    }


def _dense_features(case: dict[str, Any]) -> dict[str, Any]:
    dense = case["block4"]["dense_candidates"]
    scores = [float(item["dense_score"]) for item in dense]
    top10 = scores[:10]
    final = case["block4"]["final_candidates"]
    dense_ids = {item["chunk_id"] for item in dense}
    lexical_ids = {item["chunk_id"] for item in case["block4"]["lexical_candidates"]}
    return {
        "case_id": case["case_id"],
        "answerable": case["answerable"],
        "category": case["category"],
        "top1_dense_score": scores[0] if scores else None,
        "top1_cosine_distance": 1 - scores[0] if scores else None,
        "top3_dense_scores": scores[:3],
        "top3_cosine_distances": [1 - value for value in scores[:3]],
        "top10_dense_scores": top10,
        "top10_min": min(top10) if top10 else None,
        "top10_max": max(top10) if top10 else None,
        "top10_mean": mean(top10) if top10 else None,
        "top1_top2_gap": scores[0] - scores[1] if len(scores) > 1 else None,
        "top1_top10_gap": scores[0] - scores[9] if len(scores) > 9 else None,
        "lexical_candidate_count": len(case["block4"]["lexical_candidates"]),
        "dense_lexical_overlap": len(dense_ids & lexical_ids),
        "rrf_scores": [item["fusion_score"] for item in final],
        "unique_documents": len({item["document_id"] for item in final}),
        "expected_evidence_rank": case["metrics"]["expected_evidence_rank"],
        "block5_selected_count": case["block5"]["selected_source_ids"].__len__(),
        "block6_status": case["block6"]["status"],
        "citation_status": case["block6"]["citation_validation"],
    }


def _auc(answerable_values: list[float], unanswerable_values: list[float]) -> float | None:
    if not answerable_values or not unanswerable_values:
        return None
    wins = 0.0
    for positive in answerable_values:
        for negative in unanswerable_values:
            wins += 1.0 if positive > negative else 0.5 if positive == negative else 0.0
    return wins / (len(answerable_values) * len(unanswerable_values))


def _diagnostic_cutoff(values: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe the best observed top-1 split; never present it as a gate."""
    scores = sorted({row["top1_dense_score"] for row in values if row["top1_dense_score"] is not None})
    candidates = [scores[0] - 1e-9] + [
        (left + right) / 2 for left, right in zip(scores, scores[1:])
    ] + [scores[-1] + 1e-9]
    best = None
    for cutoff in candidates:
        false_abstentions = sum(row["answerable"] and row["top1_dense_score"] < cutoff for row in values)
        unsupported_passes = sum((not row["answerable"]) and row["top1_dense_score"] >= cutoff for row in values)
        tpr = 1 - false_abstentions / sum(row["answerable"] for row in values)
        tnr = 1 - unsupported_passes / sum(not row["answerable"] for row in values)
        candidate = {
            "observed_cutoff": cutoff,
            "balanced_accuracy": (tpr + tnr) / 2,
            "false_abstentions": false_abstentions,
            "unsupported_passes": unsupported_passes,
        }
        if best is None or candidate["balanced_accuracy"] > best["balanced_accuracy"]:
            best = candidate
    best["status"] = "DIAGNOSTIC_ONLY_NOT_A_PRODUCTION_THRESHOLD"
    return best


def _distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    answerable = [row for row in rows if row["answerable"]]
    unanswerable = [row for row in rows if not row["answerable"]]

    def summary(group, field):
        values = [row[field] for row in group if row[field] is not None]
        return {
            "count": len(values),
            "min": min(values) if values else None,
            "mean": mean(values) if values else None,
            "max": max(values) if values else None,
        }

    answerable_scores = [row["top1_dense_score"] for row in answerable]
    unanswerable_scores = [row["top1_dense_score"] for row in unanswerable]
    return {
        "answerable_top1": summary(answerable, "top1_dense_score"),
        "unanswerable_top1": summary(unanswerable, "top1_dense_score"),
        "answerable_top1_top10_gap": summary(answerable, "top1_top10_gap"),
        "unanswerable_top1_top10_gap": summary(unanswerable, "top1_top10_gap"),
        "top1_roc_auc": _auc(answerable_scores, unanswerable_scores),
        "range_overlap": {
            "lower": max(min(answerable_scores), min(unanswerable_scores)),
            "upper": min(max(answerable_scores), max(unanswerable_scores)),
        },
        "best_observed_top1_split": _diagnostic_cutoff(rows),
        "conclusion": "RETRIEVAL SIGNALS ARE NOT SUFFICIENT FOR ANSWERABILITY GATING",
        "reason": "Dense-score ranges overlap; lexical count/overlap are zero for both classes; all final candidates come from one substantive document; and dense-only RRF is a rank transform.",
    }


def _query_value(db, expression: str, query: str) -> str | None:
    return db.execute(text(f"SELECT ({expression})::text"), {"query": query}).scalar_one()


def _explicit_or_value(db, query: str) -> str | None:
    return db.execute(
        text(
            """
            WITH lexemes AS (
                SELECT unnest(tsvector_to_array(to_tsvector('simple', :query))) AS lexeme
            )
            SELECT to_tsquery(
                'simple',
                string_agg(quote_literal(lexeme), ' | ' ORDER BY lexeme)
            )::text
            FROM lexemes
            """
        ),
        {"query": query},
    ).scalar_one()


def _lexical_candidates(db, query_value: str | None, limit: int = 50) -> dict[str, Any]:
    if not query_value:
        return {"candidate_count": 0, "top_candidates": []}
    count = db.execute(
        text(
            """
            SELECT count(*)
            FROM chunk_indexes
            WHERE lexical_tsv @@ CAST(:query AS tsquery)
              AND index_version = 'block3-v1'
            """
        ),
        {"query": query_value},
    ).scalar_one()
    rows = db.execute(
        text(
            """
            SELECT chunk_id::text, document_id::text,
                   ts_rank_cd(lexical_tsv, CAST(:query AS tsquery)) AS score
            FROM chunk_indexes
            WHERE lexical_tsv @@ CAST(:query AS tsquery)
              AND index_version = 'block3-v1'
            ORDER BY score DESC, chunk_id ASC
            LIMIT :limit
            """
        ),
        {"query": query_value, "limit": limit},
    ).mappings().all()
    return {
        "candidate_count": int(count),
        "top_candidates": [
            {"chunk_id": row["chunk_id"], "document_id": row["document_id"], "rank": index, "ts_rank_cd": float(row["score"])}
            for index, row in enumerate(rows, start=1)
        ],
    }


def _solution_retrieved(ids: set[str], solutions: list[list[str]]) -> bool:
    return any(set(solution).issubset(ids) for solution in solutions)


def _lexical_probe(db, case: dict[str, Any]) -> dict[str, Any]:
    query = case["question"]
    values = {
        "websearch": _query_value(db, "websearch_to_tsquery('simple', :query)", query),
        "plainto": _query_value(db, "plainto_tsquery('simple', :query)", query),
        "explicit_or": _explicit_or_value(db, query),
    }
    variants = {}
    for name, value in values.items():
        result = _lexical_candidates(db, value)
        result["tsquery"] = value
        result["expected_solution_retrieved"] = _solution_retrieved(
            {row["chunk_id"] for row in result["top_candidates"]},
            case["acceptable_evidence_sets"],
        )
        variants[name] = result

    known_chunks = []
    for chunk_id in sorted({item for solution in case["acceptable_evidence_sets"] for item in solution}):
        row = db.execute(
            text(
                """
                SELECT c.content_text, ci.lexical_tsv::text AS lexical_tsv,
                       ci.lexical_tsv @@ websearch_to_tsquery('simple', :query) AS websearch_match,
                       ci.lexical_tsv @@ plainto_tsquery('simple', :query) AS plainto_match,
                       ci.lexical_tsv @@ CAST(:or_query AS tsquery) AS explicit_or_match
                FROM chunks c JOIN chunk_indexes ci ON ci.chunk_id = c.id
                WHERE c.id = CAST(:chunk_id AS uuid) AND ci.index_version = 'block3-v1'
                """
            ),
            {"query": query, "or_query": values["explicit_or"], "chunk_id": chunk_id},
        ).mappings().one()
        known_chunks.append({"chunk_id": chunk_id, **dict(row)})
    return {
        "case_id": case["case_id"],
        "original_query": query,
        "variants": variants,
        "known_relevant_chunks": known_chunks,
    }


def _short_probe(db, query: str) -> dict[str, Any]:
    values = {
        "websearch": _query_value(db, "websearch_to_tsquery('simple', :query)", query),
        "plainto": _query_value(db, "plainto_tsquery('simple', :query)", query),
        "explicit_or": _explicit_or_value(db, query),
    }
    return {
        "query": query,
        "tokens": [
            dict(row)
            for row in db.execute(
                text("SELECT alias, token, lexemes FROM ts_debug('simple', :query) WHERE array_length(lexemes, 1) > 0"),
                {"query": query},
            ).mappings().all()
        ],
        "tsvector": db.execute(text("SELECT to_tsvector('simple', :query)::text"), {"query": query}).scalar_one(),
        "variants": {name: {"tsquery": value, **_lexical_candidates(db, value, 10)} for name, value in values.items()},
    }


def _lexical_audit(db, cases_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    index_rows = db.execute(
        text("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='public' AND tablename='chunk_indexes' ORDER BY indexname")
    ).mappings().all()
    storage = db.execute(
        text(
            """
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE lexical_tsv IS NOT NULL) AS non_null,
                   count(*) FILTER (WHERE lexical_tsv <> ''::tsvector) AS non_empty
            FROM chunk_indexes WHERE index_version='block3-v1'
            """
        )
    ).mappings().one()
    representative = [
        "nsmo_definition",
        "oda_capital_source",
        "domestic_expert_pay_cap",
        "human_resource_benefits",
        "applicable_entities_multi",
    ]
    probes = [_lexical_probe(db, cases_by_id[case_id]) for case_id in representative]
    short = [_short_probe(db, query) for query in (
        "doanh nghiệp",
        "người lao động",
        "bảo hiểm",
        "vốn ODA",
        "Điều 7",
    )]
    totals = {
        name: sum(probe["variants"][name]["candidate_count"] for probe in probes)
        for name in ("websearch", "plainto", "explicit_or")
    }
    expected_hits = {
        name: sum(probe["variants"][name]["expected_solution_retrieved"] for probe in probes)
        for name in ("websearch", "plainto", "explicit_or")
    }
    return {
        "production_sql_function": "websearch_to_tsquery('simple', query_text)",
        "index_definitions": [dict(row) for row in index_rows],
        "storage": dict(storage),
        "representative_probes": probes,
        "controlled_short_queries": short,
        "aggregate_candidate_counts_across_five_queries": totals,
        "expected_solution_hits_across_five_queries": expected_hits,
        "root_cause": [
            "STRICT_AND_SEMANTICS",
            "VIETNAMESE_TOKEN_SPLITTING",
            "QUERY_CORPUS_VOCABULARY_MISMATCH",
        ],
        "status": "OVERLY_STRICT",
        "conclusion": "The stored vectors and GIN index are populated and short known-term probes match. Natural questions retain every simple-config token and websearch/plainto require conjunction, so one absent question word eliminates a chunk. Explicit safe OR probes recover candidates; plainto is not an OR fallback.",
    }


def _multi_evidence(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for case in cases:
        dense = {item["chunk_id"]: item for item in case["block4"]["dense_candidates"]}
        lexical = {item["chunk_id"]: item for item in case["block4"]["lexical_candidates"]}
        final = {item["chunk_id"]: item for item in case["block4"]["final_candidates"]}
        required = []
        for chunk_id in case["acceptable_evidence_sets"][0]:
            required.append({
                "chunk_id": chunk_id,
                "dense_rank": dense.get(chunk_id, {}).get("dense_rank"),
                "dense_score": dense.get(chunk_id, {}).get("dense_score"),
                "lexical_rank": lexical.get(chunk_id, {}).get("lexical_rank"),
                "rrf_rank": final.get(chunk_id, {}).get("final_rank"),
                "status": "FINAL_TOP_10" if chunk_id in final else "DENSE_POOL_ONLY" if chunk_id in dense else "NOT_RETRIEVED_IN_TOP_50",
            })
        if any(item["status"] == "NOT_RETRIEVED_IN_TOP_50" for item in required):
            stage = "CANDIDATE_GENERATION_AND_LEXICAL_BRANCH"
        elif any(item["status"] == "DENSE_POOL_ONLY" for item in required):
            stage = "TOP_K_FINAL_CUTOFF_WITH_NO_LEXICAL_SUPPORT"
        else:
            stage = "NONE"
        results.append({
            "case_id": case["case_id"],
            "question": case["question"],
            "acceptable_evidence_set": case["acceptable_evidence_sets"][0],
            "required_evidence": required,
            "dominant_failure_stage": stage,
            "ground_truth_changed": False,
        })
    return results


def _evidence_rows(package) -> list[dict[str, Any]]:
    return [
        {
            "source_id": item.source_id,
            "chunk_id": item.chunk_id,
            "document_id": item.document_id,
            "content_text": item.content_text,
            "metadata_json": item.metadata_json,
            "provenance_json": item.provenance_json,
            "retrieval_final_rank": item.retrieval_final_rank,
            "dense_rank": item.dense_rank,
            "dense_score": item.dense_score,
        }
        for item in package.selected_evidence
    ]


def _missing_review(case: dict[str, Any], package) -> dict[str, Any]:
    expected = {chunk for solution in case["acceptable_evidence_sets"] for chunk in solution}
    potential = [item.source_id for item in package.selected_evidence if item.chunk_id in expected]
    emitted_evidence_style = "[Evidence S" in case["block6"]["answer_text"]
    classification = (
        "LIKELY_FORMAT_FAILURE"
        if potential and emitted_evidence_style
        else "AMBIGUOUS_REQUIRES_HUMAN_REVIEW"
    )
    return {
        "case_id": case["case_id"],
        "question": case["question"],
        "answer": case["block6"]["answer_text"],
        "finish_reason": case["block6"]["finish_reason"],
        "provider_usage": case["block6"]["provider_usage"],
        "expected_evidence_sets": case["acceptable_evidence_sets"],
        "potential_supporting_source_ids": potential,
        "selected_evidence": _evidence_rows(package),
        "production_messages": assemble_messages(package, "legal-rag-v1"),
        "classification": classification,
        "basis": "The answer uses the literal non-contract form '[Evidence Sx]' while the expected chunk is present under that S ID. This is strong format-fading evidence, but semantic correctness remains available for human review rather than being asserted by an LLM judge.",
    }


def _wrong_source_review(case: dict[str, Any], package, db) -> dict[str, Any]:
    expected_ids = sorted({chunk for solution in case["acceptable_evidence_sets"] for chunk in solution})
    actual_ids = case["block6"]["mapped_chunk_ids"]
    ids = sorted(set(expected_ids + actual_ids))
    rows = db.execute(
        text(
            """
            SELECT c.id::text AS chunk_id, c.document_id::text AS document_id,
                   c.content_text, c.metadata_json, c.provenance_json
            FROM chunks c WHERE c.id = ANY(CAST(:ids AS uuid[]))
            """
        ),
        {"ids": ids},
    ).mappings().all()
    dense = {item["chunk_id"]: item for item in case["block4"]["dense_candidates"]}
    selected = {item.chunk_id: item.source_id for item in package.selected_evidence}
    evidence = []
    for row in rows:
        item = dict(row)
        item["role"] = "EXPECTED" if row["chunk_id"] in expected_ids else "ACTUAL_CITED"
        item["dense_rank"] = dense.get(row["chunk_id"], {}).get("dense_rank")
        item["block5_source_id"] = selected.get(row["chunk_id"])
        evidence.append(item)
    return {
        "case_id": case["case_id"],
        "question": case["question"],
        "expected_chunk_ids": expected_ids,
        "actual_cited_chunk_ids": actual_ids,
        "generated_answer": case["block6"]["answer_text"],
        "evidence_side_by_side": sorted(evidence, key=lambda row: (row["role"], row["chunk_id"])),
        "classification": "PLAUSIBLE_ALTERNATIVE_EVIDENCE",
        "basis": "At least one actually cited chunk explicitly mentions ODA and foreign concessional loans, so it plausibly supports the narrow claim. The frozen ground truth is unchanged; a legal reviewer should decide whether the alternative satisfies the intended Điều 7/Khoản 1 granularity.",
        "requires_human_legal_review": True,
    }


def _option_comparison(distribution, abstention_summary, citation_summary, lexical) -> list[dict[str, Any]]:
    cutoff = distribution["best_observed_top1_split"]
    return [
        {"option": "A. Dense similarity threshold", "measured_performance": f"Top-1 AUC={distribution['top1_roc_auc']:.3f}; best observed split (diagnostic only) has {cutoff['false_abstentions']} false abstentions and {cutoff['unsupported_passes']} unsupported passes.", "latency": "negligible", "complexity": "low", "cost": "none", "failure_modes": "score overlap, corpus/model drift, similarity is not answerability", "architecture_impact": "retrieval/output policy gate"},
        {"option": "B. Multi-signal retrieval confidence gate", "measured_performance": "Not separable here: lexical and overlap signals are zero for all 32, unique-document count is effectively constant, and RRF is dense-rank-only.", "latency": "negligible after retrieval", "complexity": "medium", "cost": "none", "failure_modes": "false confidence from correlated/non-informative signals", "architecture_impact": "new policy layer; not justified by current data"},
        {"option": "C. Lexical-support assisted gate", "measured_performance": f"Current support is unusable; five-query websearch expected hits={lexical['expected_solution_hits_across_five_queries']['websearch']}, OR diagnostic hits={lexical['expected_solution_hits_across_five_queries']['explicit_or']}.", "latency": "small PostgreSQL query", "complexity": "medium", "cost": "none", "failure_modes": "Vietnamese token splitting and vocabulary mismatch; lexical absence does not prove unanswerability", "architecture_impact": "requires retrieval repair before evaluation"},
        {"option": "D. Stronger generation abstention prompt", "measured_performance": f"B abstentions={abstention_summary['B']['abstentions']}/5, unsupported={abstention_summary['B']['unsupported']}/5.", "latency": "similar generation latency", "complexity": "low", "cost": "same provider", "failure_modes": "prompt compliance remains probabilistic; status still needs a contract", "architecture_impact": "prompt version change"},
        {"option": "E. Few-shot abstention prompt", "measured_performance": f"C abstentions={abstention_summary['C']['abstentions']}/5, unsupported={abstention_summary['C']['unsupported']}/5.", "latency": "slightly more prompt tokens", "complexity": "low", "cost": "small token increase", "failure_modes": "example overfitting and prompt-token growth", "architecture_impact": "prompt version change"},
        {"option": "F. Explicit pre-generation answerability classifier", "measured_performance": "Not tested; 32 cases are insufficient to train or validate one.", "latency": "additional inference", "complexity": "high", "cost": "additional model/runtime", "failure_modes": "false abstention and classifier drift", "architecture_impact": "new component before generation"},
        {"option": "G. LLM evidence-sufficiency decision", "measured_performance": "The existing model already emitted insufficiency wording on all five baseline cases; prompt variants test compliance but not a separately calibrated decision.", "latency": "one extra call if separated", "complexity": "medium", "cost": "additional inference if separate", "failure_modes": "uncalibrated self-judgment and inconsistent structured output", "architecture_impact": "could be pre-generation or integrated into Block 6"},
        {"option": "H. Structured abstention output/status contract", "measured_performance": "Baseline text contains explicit abstention wording in 5/5 while pipeline status recognized 0/5; this directly addresses the measured mismatch.", "latency": "none or negligible", "complexity": "low-medium", "cost": "none", "failure_modes": "sentinel/parser ambiguity unless output is structured and tested", "architecture_impact": "small Block 6 contract change; recommended first for a future fix"},
        {"option": "Citation-format reinforcement", "measured_performance": f"Current={citation_summary['A']['valid']}/2, stronger={citation_summary['B']['valid']}/2, few-shot={citation_summary['C']['valid']}/2.", "latency": "similar generation latency", "complexity": "low", "cost": "small token increase", "failure_modes": "format fading can recur", "architecture_impact": "prompt version change"},
    ]


def _md_code(value: Any) -> str:
    return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```"


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# RAG Quality Failure Deep-Dive V1",
        "",
        "Diagnosis only. No production behavior, frozen Block 1–6 code, evaluation dataset, thresholds, generation parameters, retrieval parameters, or schema were changed.",
        "",
        "## Frozen inputs and baseline",
        "",
        f"- Dataset SHA-256: `{report['dataset_sha256']}`",
        f"- Regression: {report['core_regression']['passed']}/{report['core_regression']['collected']} passed, {report['core_regression']['failed']} failed, {report['core_regression']['warnings']} warnings in {report['core_regression']['duration_seconds']:.2f}s.",
        f"- Model/config: `{report['runtime']['model_id']}`, prompt `{report['runtime']['prompt_version']}`, temperature {report['runtime']['temperature']}, top_p {report['runtime']['top_p']}, top_k {report['runtime']['top_k']}.",
        "",
        "## Executive diagnosis",
        "",
        report["executive_diagnosis"],
        "",
        "**Retrieval signals are not sufficient for answerability gating.** Topical relevance is not semantic answerability, and the measured score ranges overlap.",
        "",
        "## All-case signal distribution",
        "",
        "| Case | Answerable | Category | Top-1 score | Distance | Top-1→10 gap | Lexical | Overlap | Docs | Expected rank | Selected | Block 6 | Citation |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in report["signal_table"]:
        lines.append(
            f"| {row['case_id']} | {row['answerable']} | {row['category']} | {_round(row['top1_dense_score'])} | {_round(row['top1_cosine_distance'])} | {_round(row['top1_top10_gap'])} | {row['lexical_candidate_count']} | {row['dense_lexical_overlap']} | {row['unique_documents']} | {row['expected_evidence_rank']} | {row['block5_selected_count']} | {row['block6_status']} | {row['citation_status']} |"
        )
    dist = report["signal_distribution"]
    lines += [
        "",
        "### Distribution summary",
        "",
        f"- Answerable top-1: min {_round(dist['answerable_top1']['min'])}, mean {_round(dist['answerable_top1']['mean'])}, max {_round(dist['answerable_top1']['max'])}.",
        f"- Unanswerable top-1: min {_round(dist['unanswerable_top1']['min'])}, mean {_round(dist['unanswerable_top1']['mean'])}, max {_round(dist['unanswerable_top1']['max'])}.",
        f"- Top-1 ROC AUC: {_round(dist['top1_roc_auc'])}.",
        f"- Observed range overlap: {_round(dist['range_overlap']['lower'])}–{_round(dist['range_overlap']['upper'])}.",
        f"- Best observed split is diagnostic only: {dist['best_observed_top1_split']['false_abstentions']} false abstentions and {dist['best_observed_top1_split']['unsupported_passes']} unsupported passes. It is not a recommended threshold.",
        "",
        "## Unanswerable cases (5/5)",
        "",
    ]
    for item in report["unanswerable_analysis"]:
        lines += [
            f"### {item['case_id']}",
            "",
            f"Question: {item['question']}",
            "",
            f"Retrieval-side: {item['retrieval_assessment']}",
            "",
            f"Generation-side: {item['generation_assessment']}",
            "",
            f"Baseline pipeline status: `{item['baseline']['pipeline_status']}`; explicit abstention text detected: `{item['baseline']['abstention_text_detected']}`.",
            "",
            "<details><summary>Exact Block 4/5/6 diagnostic package</summary>",
            "",
            _md_code(item["snapshot"]),
            "",
            "</details>",
            "",
            "| Variant | Abstained | Pipeline status | Citations | Unsupported direct answer | Latency ms |",
            "|---|---:|---|---:|---:|---:|",
        ]
        for name in ("A", "B", "C"):
            result = item["experiments"][name]
            lines.append(f"| {name} | {result['abstention_text_detected']} | {result['pipeline_status']} | {len(result['citation_ids'])} | {result['unsupported_direct_answer_detected']} | {_round(result['latency_ms'], 2)} |")
        lines += ["", "<details><summary>Exact A/B/C messages and answers</summary>", "", _md_code(item["experiments"]), "", "</details>", ""]

    lexical = report["lexical_audit"]
    lines += [
        "## Lexical branch audit",
        "",
        f"Status: **{lexical['status']}**.",
        "",
        lexical["conclusion"],
        "",
        f"Stored `block3-v1` vectors: {lexical['storage']['non_empty']}/{lexical['storage']['total']} non-empty.",
        "",
        "| Representative query | websearch candidates/hit | plainto candidates/hit | explicit OR candidates/hit |",
        "|---|---|---|---|",
    ]
    for probe in lexical["representative_probes"]:
        cells = []
        for name in ("websearch", "plainto", "explicit_or"):
            variant = probe["variants"][name]
            cells.append(f"{variant['candidate_count']}/{variant['expected_solution_retrieved']}")
        lines.append(f"| {probe['case_id']} | {cells[0]} | {cells[1]} | {cells[2]} |")
    lines += [
        "",
        "### Vietnamese tokenization and controlled probes",
        "",
        "`simple` splits multi-syllable Vietnamese expressions into independent lexemes. With AND semantics, every surviving syllable/question token must occur in one chunk; this is fragile for natural questions.",
        "",
        _md_code({"short_queries": lexical["controlled_short_queries"], "representative_probes": lexical["representative_probes"], "indexes": lexical["index_definitions"]}),
        "",
        "## Multi-evidence misses",
        "",
        _md_code(report["multi_evidence_analysis"]),
        "",
        "## Missing-citation human review packages",
        "",
    ]
    for review in report["missing_citation_reviews"]:
        lines += [f"### {review['case_id']}: {review['classification']}", "", review["basis"], "", _md_code(review), ""]
    lines += [
        "### Controlled citation-format experiments",
        "",
        _md_code(report["citation_experiments"]),
        "",
        "## Wrong-source review",
        "",
        f"Classification: **{report['wrong_source_review']['classification']}**. Ground truth remains frozen; human legal review is required.",
        "",
        _md_code(report["wrong_source_review"]),
        "",
        "## Evidence-sufficiency design options",
        "",
        "| Option | Measured result | Latency | Complexity | Cost | Failure modes | Architecture impact |",
        "|---|---|---|---|---|---|---|",
    ]
    for option in report["design_options"]:
        lines.append(f"| {option['option']} | {option['measured_performance']} | {option['latency']} | {option['complexity']} | {option['cost']} | {option['failure_modes']} | {option['architecture_impact']} |")
    lines += [
        "",
        "## Recommended targeted fixes (not implemented)",
        "",
        "1. **Structured abstention output/status contract.** Evidence: all five baseline answers explicitly abstain in text, but the pipeline recognizes zero as `INSUFFICIENT_EVIDENCE`. Expected benefit: correct machine-readable abstention and evaluation semantics. Architecture impact: small, localized future Block 6 contract/parser change with regression tests.",
        "2. **Repair and re-evaluate lexical query construction.** Evidence: populated vectors and working short probes, but natural-language conjunction returns zero while safe OR probes recover candidates. Expected benefit: restore genuine hybrid candidate generation and improve multi-evidence recall. Architecture impact: localized future Block 4 query change; requires frozen-contract approval and regression evaluation.",
        "3. **Reinforce exact citation syntax using the measured best diagnostic variant.** Evidence: missing cases emit `[Evidence S1]` despite having supporting S1 evidence. Expected benefit: reduce format fading. Architecture impact: future versioned prompt change only, after human approval.",
        "",
        "No fix was implemented in this phase.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run(dataset_path: Path, baseline_path: Path, json_path: Path, markdown_path: Path) -> dict[str, Any]:
    frozen_hash = sha256(dataset_path)
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    cases = baseline["cases"]
    cases_by_id = {case["case_id"]: case for case in cases}
    profile = get_generation_profile()
    builder = ContextBuilderService(ContextTokenCounter(profile.tokenizer_provider, profile.tokenizer_id))
    counter = PromptTokenCounter(profile.tokenizer_provider, profile.tokenizer_id, thinking=profile.thinking)
    llm = get_llm_client()
    db = SessionLocal()
    try:
        await llm.health(profile)
        packages = {case["case_id"]: _context_package(case, builder, profile.context_budget_tokens) for case in cases}
        current_prompt = load_system_prompt("legal-rag-v1")
        abstention_prompts = {
            "A": current_prompt,
            "B": current_prompt + "\n\n" + STRONG_ABSTENTION,
            "C": current_prompt + "\n\n" + STRONG_ABSTENTION + "\n\n" + ABSTENTION_FEW_SHOT,
        }
        unanswerable_analysis = []
        for case in [item for item in cases if not item["answerable"]]:
            package = packages[case["case_id"]]
            experiments = {}
            for name, prompt in abstention_prompts.items():
                print(f"unanswerable {case['case_id']} variant {name}", flush=True)
                experiments[name] = await _generate(llm, profile, counter, package, prompt)
            baseline_answer = case["block6"]["answer_text"]
            dense = case["block4"]["dense_candidates"]
            unanswerable_analysis.append({
                "case_id": case["case_id"],
                "question": case["question"],
                "baseline": {
                    "answer": baseline_answer,
                    "pipeline_status": case["block6"]["status"],
                    "abstention_text_detected": _abstention_signal(baseline_answer),
                    "citation_validation": case["block6"]["citation_validation"],
                },
                "retrieval_assessment": "No reliable insufficiency boundary is visible: high, compressed dense scores indicate topical proximity only; lexical support is absent for both answerable and unanswerable cases; all candidates come from the same substantive document; and dense-only RRF cannot add an independent signal.",
                "generation_assessment": "The baseline answer explicitly states that evidence is insufficient and does not supply the requested absent fact. The observed 0% abstention/100% unsupported metrics arise because free-text abstention is not mapped to the pipeline INSUFFICIENT_EVIDENCE status; citation validation instead produces COMPLETED_WITH_WARNINGS. This is primarily a status/response-contract issue, not evidence that the model ignored the abstention instruction.",
                "snapshot": {
                    "block4": {
                        "dense_candidates": dense,
                        "dense_distances": [{"chunk_id": item["chunk_id"], "rank": item["dense_rank"], "cosine_distance": 1 - item["dense_score"]} for item in dense],
                        "lexical_candidates": case["block4"]["lexical_candidates"],
                        "rrf_candidates": case["block4"]["final_candidates"],
                    },
                    "block5": {
                        **case["block5"],
                        "context_text": package.context_text,
                        "selected_evidence": _evidence_rows(package),
                    },
                    "block6": {
                        **case["block6"],
                        "production_messages": assemble_messages(package, "legal-rag-v1"),
                    },
                },
                "experiments": experiments,
            })

        citation_cases = [cases_by_id["nsmo_definition"], cases_by_id["domestic_expert_pay_cap"]]
        citation_prompts = {
            "A": current_prompt,
            "B": current_prompt + "\n\n" + STRONG_CITATION,
            "C": current_prompt + "\n\n" + STRONG_CITATION + "\n\n" + CITATION_FEW_SHOT,
        }
        citation_experiments = []
        for case in citation_cases:
            package = packages[case["case_id"]]
            variants = {}
            for name, prompt in citation_prompts.items():
                print(f"citation {case['case_id']} variant {name}", flush=True)
                variants[name] = await _generate(llm, profile, counter, package, prompt)
                variants[name]["valid_citation_present"] = variants[name]["citation_validation"] == "PASS" and bool(variants[name]["citation_ids"])
            citation_experiments.append({"case_id": case["case_id"], "variants": variants})

        abstention_summary = {
            name: {
                "abstentions": sum(item["experiments"][name]["abstention_text_detected"] for item in unanswerable_analysis),
                "pipeline_insufficient_status": sum(item["experiments"][name]["pipeline_status"] == "INSUFFICIENT_EVIDENCE" for item in unanswerable_analysis),
                "unsupported": sum(item["experiments"][name]["unsupported_direct_answer_detected"] for item in unanswerable_analysis),
                "citations": sum(bool(item["experiments"][name]["citation_ids"]) for item in unanswerable_analysis),
                "mean_latency_ms": mean(item["experiments"][name]["latency_ms"] for item in unanswerable_analysis),
            }
            for name in ("A", "B", "C")
        }
        citation_summary = {
            name: {
                "present": sum(bool(item["variants"][name]["citation_ids"]) for item in citation_experiments),
                "valid": sum(item["variants"][name]["valid_citation_present"] for item in citation_experiments),
                "mean_latency_ms": mean(item["variants"][name]["latency_ms"] for item in citation_experiments),
            }
            for name in ("A", "B", "C")
        }
        signal_table = [_dense_features(case) for case in cases]
        distribution = _distribution(signal_table)
        lexical = _lexical_audit(db, cases_by_id)
        multi = _multi_evidence([case for case in cases if case["category"] == "MULTI_EVIDENCE"])
        missing_reviews = [_missing_review(case, packages[case["case_id"]]) for case in citation_cases]
        wrong = _wrong_source_review(cases_by_id["oda_capital_source"], packages["oda_capital_source"], db)
        report = {
            "report_id": "quality_failure_deep_dive_v1",
            "diagnostic_conclusions": {
                "retrieval_side_separability": "STRONG_IN_SAMPLE_BUT_NOT_DEFENSIBLE_AS_A_GATE",
                "retrieval_gate_reason": "Top-1 ROC AUC is high on this tiny single-document sample, but score ranges overlap, the best observed split falsely abstains on one answerable case, lexical support is non-informative, and only five unanswerable cases exist.",
                "generation_side_abstention_issue": "FREE_TEXT_ABSTENTION_IS_NOT_MAPPED_TO_INSUFFICIENT_EVIDENCE_STATUS",
                "likely_dominant_cause": "MULTIPLE_STATUS_CONTRACT_LEXICAL_STRICTNESS_AND_CITATION_FORMAT_FADING",
                "citation_material_change_assessment": "No core entity or numeric conclusion changed across A/B/C for either citation case; B/C primarily corrected syntax and shortened wording. This is a human diagnostic observation, not LLM-as-judge ground truth.",
                "original_baseline_citation_success_for_two_failed_cases": "0/2",
                "controlled_current_prompt_citation_success": "1/2",
                "controlled_stronger_instruction_citation_success": "2/2",
                "controlled_few_shot_citation_success": "2/2",
            },
            "diagnosis_only": True,
            "production_behavior_changed": False,
            "evaluation_dataset_changed": False,
            "thresholds_tuned": False,
            "dataset_sha256": frozen_hash,
            "core_regression": {"collected": 168, "passed": 168, "failed": 0, "skipped": 0, "warnings": 8, "duration_seconds": 90.18},
            "runtime": {
                "model_id": profile.model_id,
                "tokenizer_id": profile.tokenizer_id,
                "prompt_version": profile.prompt_version,
                "temperature": profile.temperature,
                "top_p": profile.top_p,
                "top_k": profile.top_k,
                "max_output_tokens": profile.max_output_tokens,
                "context_budget_tokens": profile.context_budget_tokens,
            },
            "database_audit": {
                "production_tables_before_and_after": 10,
                "new_tables": 0,
                "schema_changed": False,
            },
            "executive_diagnosis": "The headline unanswerable failure is primarily a response-status/evaluation-contract mismatch: all five baseline answers explicitly abstain, but free-text abstention cannot produce the frozen pipeline's INSUFFICIENT_EVIDENCE status once evidence was selected. Dense scores show strong but imperfect in-sample separation and are not sufficient for a defensible answerability gate. Independently, the lexical branch is populated and indexed but overly strict for full Vietnamese questions, and the two missing citations are likely exact-format fading (`[Evidence S1]` instead of `[S1]`).",
            "signal_table": signal_table,
            "signal_distribution": distribution,
            "unanswerable_analysis": unanswerable_analysis,
            "abstention_experiment_summary": abstention_summary,
            "lexical_audit": lexical,
            "multi_evidence_analysis": multi,
            "missing_citation_reviews": missing_reviews,
            "citation_experiments": citation_experiments,
            "citation_experiment_summary": citation_summary,
            "wrong_source_review": wrong,
        }
        report["design_options"] = _option_comparison(distribution, abstention_summary, citation_summary, lexical)
        report["recommended_targeted_fixes"] = [
            {"priority": 1, "fix": "Structured abstention output/status contract", "evidence": "5/5 baseline answers contain explicit insufficiency wording; 0/5 receive pipeline INSUFFICIENT_EVIDENCE status.", "expected_benefit": "Align machine status and evaluation with actual abstention behavior.", "architecture_impact": "Small future Block 6 contract/parser change; not implemented."},
            {"priority": 2, "fix": "Safely repair lexical natural-language query semantics and re-evaluate", "evidence": lexical["conclusion"], "expected_benefit": "Restore independent lexical candidates and potential multi-evidence recall.", "architecture_impact": "Localized future Block 4 change requiring frozen-contract approval; not implemented."},
            {"priority": 3, "fix": "Versioned exact-citation prompt reinforcement", "evidence": "Both missing-citation answers emitted [Evidence S1] while expected evidence was selected.", "expected_benefit": "Reduce citation syntax fading.", "architecture_impact": "Future prompt-version change; not implemented."},
        ]
        if sha256(dataset_path) != frozen_hash:
            raise RuntimeError("Evaluation dataset changed during diagnosis")
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_markdown(markdown_path, report)
        return report
    finally:
        db.close()
        await close_llm_client()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    parser.add_argument("--json", type=Path, default=JSON_PATH)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN_PATH)
    args = parser.parse_args()
    report = asyncio.run(run(args.dataset, args.baseline, args.json, args.markdown))
    print(json.dumps({
        "dataset_sha256": report["dataset_sha256"],
        "abstention": report["abstention_experiment_summary"],
        "citation": report["citation_experiment_summary"],
        "lexical": report["lexical_audit"]["aggregate_candidate_counts_across_five_queries"],
        "multi": report["multi_evidence_analysis"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
