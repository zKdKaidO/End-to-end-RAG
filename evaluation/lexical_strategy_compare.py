"""Offline comparison of lexical query semantics on the frozen evaluation set."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from time import perf_counter
from uuid import UUID

from sqlalchemy import text

from app.db.database import SessionLocal
from app.retrieval.rrf import reciprocal_rank_fusion
from app.retrieval.types import DenseCandidate, LexicalCandidate
from evaluation.retrieval_metrics import hit_at_k, reciprocal_rank


BASELINE = Path("evaluation/reports/legal_eval_v1.json")
OUTPUT = Path("evaluation/reports/lexical_strategy_comparison_v1.json")


STRICT_SQL = """
WITH lexical_query AS (
    SELECT websearch_to_tsquery('simple', :query_text) AS value
)
SELECT ci.chunk_id, ci.document_id,
       ts_rank_cd(ci.lexical_tsv, lexical_query.value) AS lexical_score
FROM chunk_indexes ci CROSS JOIN lexical_query
WHERE ci.lexical_tsv @@ lexical_query.value
  AND ci.index_version = 'block3-v1'
  AND (:has_filter = FALSE OR ci.document_id = ANY(CAST(:document_ids AS uuid[])))
ORDER BY lexical_score DESC, ci.chunk_id ASC
LIMIT 50
"""


OR_SQL = """
WITH normalized_lexemes AS (
    SELECT DISTINCT unnest(tsvector_to_array(to_tsvector('simple', :query_text))) AS lexeme
), lexical_query AS (
    SELECT CASE
        WHEN count(*) = 0 THEN NULL::tsquery
        ELSE to_tsquery(
            'simple',
            string_agg(quote_literal(lexeme), ' | ' ORDER BY lexeme)
        )
    END AS value
    FROM normalized_lexemes
)
SELECT ci.chunk_id, ci.document_id,
       ts_rank_cd(ci.lexical_tsv, lexical_query.value) AS lexical_score
FROM chunk_indexes ci CROSS JOIN lexical_query
WHERE lexical_query.value IS NOT NULL
  AND ci.lexical_tsv @@ lexical_query.value
  AND ci.index_version = 'block3-v1'
  AND (:has_filter = FALSE OR ci.document_id = ANY(CAST(:document_ids AS uuid[])))
ORDER BY lexical_score DESC, ci.chunk_id ASC
LIMIT 50
"""


SALIENT_OR_SQL = """
WITH normalized_lexemes AS (
    SELECT DISTINCT unnest(tsvector_to_array(to_tsvector('simple', :query_text))) AS lexeme
), lexeme_stats AS (
    SELECT nl.lexeme, count(ci.chunk_id) AS document_frequency
    FROM normalized_lexemes nl
    JOIN chunk_indexes ci
      ON ci.lexical_tsv @@ to_tsquery('simple', quote_literal(nl.lexeme))
     AND ci.index_version = 'block3-v1'
     AND (:has_filter = FALSE OR ci.document_id = ANY(CAST(:document_ids AS uuid[])))
    GROUP BY nl.lexeme
), selected_lexemes AS (
    SELECT lexeme
    FROM lexeme_stats
    WHERE document_frequency > 0
    ORDER BY document_frequency ASC, lexeme ASC
    LIMIT 8
), lexical_query AS (
    SELECT CASE
        WHEN count(*) = 0 THEN NULL::tsquery
        ELSE to_tsquery(
            'simple',
            string_agg(quote_literal(lexeme), ' | ' ORDER BY lexeme)
        )
    END AS value
    FROM selected_lexemes
), candidates AS (
    SELECT ci.chunk_id, ci.document_id,
           ts_rank_cd(ci.lexical_tsv, lexical_query.value) AS lexical_score,
           (
               SELECT count(*)
               FROM selected_lexemes sl
               WHERE ci.lexical_tsv @@ to_tsquery('simple', quote_literal(sl.lexeme))
           ) AS matched_lexeme_count
    FROM chunk_indexes ci CROSS JOIN lexical_query
    WHERE lexical_query.value IS NOT NULL
      AND ci.lexical_tsv @@ lexical_query.value
      AND ci.index_version = 'block3-v1'
      AND (:has_filter = FALSE OR ci.document_id = ANY(CAST(:document_ids AS uuid[])))
)
SELECT chunk_id, document_id, lexical_score
FROM candidates
ORDER BY matched_lexeme_count DESC, lexical_score DESC, chunk_id ASC
LIMIT 50
"""


RARE_AND_SQL = """
WITH normalized_lexemes AS (
    SELECT DISTINCT unnest(tsvector_to_array(to_tsvector('simple', :query_text))) AS lexeme
), lexeme_stats AS (
    SELECT nl.lexeme, count(ci.chunk_id) AS document_frequency
    FROM normalized_lexemes nl
    JOIN chunk_indexes ci
      ON ci.lexical_tsv @@ to_tsquery('simple', quote_literal(nl.lexeme))
     AND ci.index_version = 'block3-v1'
     AND (:has_filter = FALSE OR ci.document_id = ANY(CAST(:document_ids AS uuid[])))
    GROUP BY nl.lexeme
), selected_lexemes AS (
    SELECT lexeme
    FROM lexeme_stats
    WHERE document_frequency > 0
    ORDER BY document_frequency ASC, lexeme ASC
    LIMIT :lexeme_limit
), lexical_query AS (
    SELECT CASE
        WHEN count(*) = 0 THEN NULL::tsquery
        ELSE to_tsquery(
            'simple',
            string_agg(quote_literal(lexeme), ' & ' ORDER BY lexeme)
        )
    END AS value
    FROM selected_lexemes
)
SELECT ci.chunk_id, ci.document_id,
       ts_rank_cd(ci.lexical_tsv, lexical_query.value) AS lexical_score
FROM chunk_indexes ci CROSS JOIN lexical_query
WHERE lexical_query.value IS NOT NULL
  AND ci.lexical_tsv @@ lexical_query.value
  AND ci.index_version = 'block3-v1'
  AND (:has_filter = FALSE OR ci.document_id = ANY(CAST(:document_ids AS uuid[])))
ORDER BY lexical_score DESC, ci.chunk_id ASC
LIMIT 50
"""


def _search(db, sql: str, case: dict, **extra_params) -> tuple[list[LexicalCandidate], float]:
    document_ids = case.get("document_ids") or []
    started = perf_counter()
    rows = db.execute(
        text(sql),
        {
            "query_text": case["question"],
            "has_filter": bool(document_ids),
            "document_ids": document_ids or None,
            **extra_params,
        },
    ).mappings().all()
    elapsed = (perf_counter() - started) * 1000
    return [
        LexicalCandidate(
            chunk_id=row["chunk_id"],
            document_id=row["document_id"],
            lexical_score=float(row["lexical_score"]),
            lexical_rank=rank,
        )
        for rank, row in enumerate(rows, start=1)
    ], elapsed


def _dense(case: dict) -> list[DenseCandidate]:
    return [
        DenseCandidate(
            chunk_id=UUID(item["chunk_id"]),
            document_id=UUID(item["document_id"]),
            dense_score=item["dense_score"],
            dense_rank=item["dense_rank"],
        )
        for item in case["block4"]["dense_candidates"]
    ]


def _solution_present(ids: list[str], solutions: list[list[str]]) -> bool:
    available = set(ids)
    return any(set(solution).issubset(available) for solution in solutions)


def main() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    cases = baseline["cases"]
    db = SessionLocal()
    try:
        details = {name: [] for name in ("strict_websearch", "safe_or", "strict_first_or_fallback", "salient_or_fallback", "rarest_1_fallback", "rarest_2_and_fallback", "rarest_3_and_fallback", "rarest_4_and_fallback", "rarest_5_and_fallback")}
        for case in cases:
            strict, strict_ms = _search(db, STRICT_SQL, case)
            safe_or, or_ms = _search(db, OR_SQL, case)
            salient_or, salient_ms = _search(db, SALIENT_OR_SQL, case)
            rare1, rare1_ms = _search(db, RARE_AND_SQL, case, lexeme_limit=1)
            rare2, rare2_ms = _search(db, RARE_AND_SQL, case, lexeme_limit=2)
            rare3, rare3_ms = _search(db, RARE_AND_SQL, case, lexeme_limit=3)
            rare4, rare4_ms = _search(db, RARE_AND_SQL, case, lexeme_limit=4)
            rare5, rare5_ms = _search(db, RARE_AND_SQL, case, lexeme_limit=5)
            variants = {
                "strict_websearch": (strict, strict_ms),
                "safe_or": (safe_or, or_ms),
                "strict_first_or_fallback": (strict, strict_ms) if strict else (safe_or, strict_ms + or_ms),
                "salient_or_fallback": (strict, strict_ms) if strict else (salient_or, strict_ms + salient_ms),
                "rarest_1_fallback": (strict, strict_ms) if strict else (rare1, strict_ms + rare1_ms),
                "rarest_2_and_fallback": (strict, strict_ms) if strict else (rare2, strict_ms + rare2_ms),
                "rarest_3_and_fallback": (strict, strict_ms) if strict else (rare3, strict_ms + rare3_ms),
                "rarest_4_and_fallback": (strict, strict_ms) if strict else (rare4, strict_ms + rare4_ms),
                "rarest_5_and_fallback": (strict, strict_ms) if strict else (rare5, strict_ms + rare5_ms),
            }
            dense = _dense(case)
            for name, (lexical, elapsed) in variants.items():
                fused = reciprocal_rank_fusion(dense, lexical, 60, 10)
                final_ids = [str(item.chunk_id) for item in fused]
                lexical_ids = [str(item.chunk_id) for item in lexical]
                answerable = case["answerable"]
                details[name].append({
                    "case_id": case["case_id"],
                    "answerable": answerable,
                    "category": case["category"],
                    "lexical_count": len(lexical),
                    "lexical_ids": lexical_ids,
                    "lexical_scores": [item.lexical_score for item in lexical],
                    "lexical_expected_solution": _solution_present(lexical_ids, case["acceptable_evidence_sets"]) if answerable else None,
                    "final_ids": final_ids,
                    "expected_rank": next((rank for rank in range(1, 11) if hit_at_k(final_ids, case["acceptable_evidence_sets"], rank)), None) if answerable else None,
                    "rr": reciprocal_rank(final_ids, case["acceptable_evidence_sets"]) if answerable else None,
                    "latency_ms": elapsed,
                })
        report = {"report_id": "lexical_strategy_comparison_v1", "dataset_case_count": len(cases), "strategies": {}}
        for name, rows in details.items():
            answerable = [row for row in rows if row["answerable"]]
            report["strategies"][name] = {
                "lexical_non_empty_rate": sum(row["lexical_count"] > 0 for row in rows) / len(rows),
                "lexical_expected_solution_rate": sum(row["lexical_expected_solution"] for row in answerable) / len(answerable),
                "average_candidate_count": mean(row["lexical_count"] for row in rows),
                "average_latency_ms": mean(row["latency_ms"] for row in rows),
                "hit_at_1": sum(row["expected_rank"] is not None and row["expected_rank"] <= 1 for row in answerable) / len(answerable),
                "hit_at_3": sum(row["expected_rank"] is not None and row["expected_rank"] <= 3 for row in answerable) / len(answerable),
                "hit_at_5": sum(row["expected_rank"] is not None and row["expected_rank"] <= 5 for row in answerable) / len(answerable),
                "hit_at_10": sum(row["expected_rank"] is not None and row["expected_rank"] <= 10 for row in answerable) / len(answerable),
                "mrr": mean(row["rr"] for row in answerable),
                "multi_evidence": [row for row in rows if row["category"] == "MULTI_EVIDENCE"],
                "cases": rows,
            }
        report["decision_rule"] = "Select only a strategy that restores non-empty lexical retrieval while preserving or improving frozen overall Hit@K/MRR; returning more candidates alone is insufficient."
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({name: {key: value for key, value in data.items() if key not in {"cases", "multi_evidence"}} for name, data in report["strategies"].items()}, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
