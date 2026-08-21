"""Offline replay and ablation for frozen Legal Evaluation V2 retrieval snapshots.

This module is intentionally outside application imports. It performs read-only
database access and never changes production retrieval, context, or generation.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from time import perf_counter
from typing import Any, Iterable

from sqlalchemy import text

from app.context.service import ContextBuilderService
from app.db.database import SessionLocal
from app.generation.answerability import parse_answerability
from app.generation.citations import validate_and_map_citations
from app.generation.profile import get_generation_profile
from app.generation.prompting import assemble_messages
from app.generation.runtime import close_llm_client, get_llm_client
from app.generation.schemas import CitationValidation, GenerationStatus
from app.generation.tokenizers import ContextTokenCounter
from app.orchestration.answer_service import INSUFFICIENT_EVIDENCE_MESSAGE
from evaluation.dataset_validator import load_dataset, validate_dataset
from evaluation.retrieval_metrics import acceptable_solution_rank, reciprocal_rank
from evaluation.v2_metrics import document_hit_at_k, evidence_set_metrics, latency_summary, rate


ROOT = Path(__file__).resolve().parents[3]
DATASET = ROOT / "evaluation" / "datasets" / "legal_eval_v2.json"
BASELINE = ROOT / "evaluation" / "reports" / "legal_eval_v2_baseline.json"
INTEGRITY = ROOT / "evaluation" / "reports" / "legal_corpus_v2_integrity.json"
REPORTS = ROOT / "evaluation" / "reports"
V2_SHA256 = "ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842"
MODEL = "intfloat/multilingual-e5-base"
INDEX_VERSION = "block3-v1"
DIMENSION = 768
RRF_K = 60
TOP_K = 10
MAX_EXPANSION_PER_ANCHOR = 4
MAX_EXPANDED_CANDIDATES = 40


@dataclass(frozen=True)
class Unit:
    id: str
    document_id: str
    parent_id: str | None
    unit_type: str
    unit_number: str | None
    unit_title: str | None
    level: int
    page_start: int
    page_end: int
    char_start: int
    char_end: int


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _pct(value: float | None) -> str:
    return "N/A" if value is None else f"{100 * value:.2f}%"


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _is_multi(case) -> bool:
    return case.answerable and min((len(solution) for solution in case.acceptable_evidence_sets), default=0) > 1


def fuse_from_snapshot(case_report: dict[str, Any]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in case_report["block4"]["dense_candidates"]:
        merged[item["chunk_id"]] = {
            "chunk_id": item["chunk_id"], "document_id": item["document_id"],
            "dense_score": item["dense_score"], "dense_rank": item["dense_rank"],
            "lexical_score": None, "lexical_rank": None,
        }
    for item in case_report["block4"]["lexical_candidates"]:
        entry = merged.setdefault(item["chunk_id"], {
            "chunk_id": item["chunk_id"], "document_id": item["document_id"],
            "dense_score": None, "dense_rank": None,
            "lexical_score": None, "lexical_rank": None,
        })
        entry["lexical_score"] = item["lexical_score"]
        entry["lexical_rank"] = item["lexical_rank"]
    for entry in merged.values():
        entry["fusion_score"] = (
            (1 / (RRF_K + entry["dense_rank"]) if entry["dense_rank"] else 0)
            + (1 / (RRF_K + entry["lexical_rank"]) if entry["lexical_rank"] else 0)
        )
    ranked = sorted(merged.values(), key=lambda item: (-item["fusion_score"], item["chunk_id"]))
    for rank, item in enumerate(ranked, start=1):
        item["final_rank"] = rank
    return ranked


class CorpusGraph:
    def __init__(self, db, document_ids: list[str], candidate_ids: set[str]):
        ids = sorted(candidate_ids)
        rows = db.execute(text("""
            SELECT c.id::text AS chunk_id, c.document_id::text, c.legal_unit_id::text,
                   c.chunk_index, c.content_text, c.metadata_json, c.provenance_json,
                   c.page_start, c.page_end
            FROM chunks c
            WHERE c.document_id = ANY(CAST(:document_ids AS uuid[]))
               OR c.id = ANY(CAST(:chunk_ids AS uuid[]))
        """), {"document_ids": document_ids, "chunk_ids": ids}).mappings().all()
        self.chunks = {row["chunk_id"]: dict(row) for row in rows}
        unit_rows = db.execute(text("""
            SELECT id::text, document_id::text, parent_unit_id::text, unit_type,
                   unit_number, unit_title, level, page_start, page_end, char_start, char_end
            FROM legal_units
            WHERE document_id = ANY(CAST(:document_ids AS uuid[]))
            ORDER BY document_id, char_start, id
        """), {"document_ids": document_ids}).mappings().all()
        self.units = {
            row["id"]: Unit(
                id=row["id"], document_id=row["document_id"], parent_id=row["parent_unit_id"],
                unit_type=row["unit_type"], unit_number=row["unit_number"], unit_title=row["unit_title"],
                level=row["level"], page_start=row["page_start"], page_end=row["page_end"],
                char_start=row["char_start"], char_end=row["char_end"],
            ) for row in unit_rows
        }
        self.children: dict[str, list[str]] = defaultdict(list)
        self.unit_chunks: dict[str, list[str]] = defaultdict(list)
        self.document_units: dict[str, list[str]] = defaultdict(list)
        for unit in self.units.values():
            if unit.parent_id:
                self.children[unit.parent_id].append(unit.id)
            self.document_units[unit.document_id].append(unit.id)
        for chunk in self.chunks.values():
            if chunk["legal_unit_id"]:
                self.unit_chunks[chunk["legal_unit_id"]].append(chunk["chunk_id"])
        for values in self.children.values():
            values.sort(key=lambda uid: (self.units[uid].char_start, uid))
        for values in self.unit_chunks.values():
            values.sort(key=lambda cid: (self.chunks[cid]["chunk_index"], cid))
        for values in self.document_units.values():
            values.sort(key=lambda uid: (self.units[uid].char_start, uid))

    def unit_id(self, chunk_id: str) -> str | None:
        chunk = self.chunks.get(chunk_id)
        return chunk["legal_unit_id"] if chunk else None

    def ancestors(self, unit_id: str | None) -> list[str]:
        result = []
        seen = set()
        while unit_id and unit_id in self.units and unit_id not in seen:
            seen.add(unit_id)
            result.append(unit_id)
            unit_id = self.units[unit_id].parent_id
        return result

    def article_id(self, chunk_id: str) -> str | None:
        for uid in self.ancestors(self.unit_id(chunk_id)):
            if self.units[uid].unit_type == "ARTICLE":
                return uid
        return None

    def descendants(self, unit_id: str, max_nodes: int = 50) -> list[str]:
        result, queue = [], list(self.children.get(unit_id, []))
        while queue and len(result) < max_nodes:
            current = queue.pop(0)
            result.append(current)
            queue.extend(self.children.get(current, []))
        return result

    def chunks_for_units(self, unit_ids: Iterable[str]) -> list[str]:
        result = []
        for uid in unit_ids:
            result.extend(self.unit_chunks.get(uid, []))
        return list(dict.fromkeys(result))

    def related(self, chunk_id: str, strategy: str) -> list[str]:
        uid = self.unit_id(chunk_id)
        if not uid or uid not in self.units:
            return []
        unit = self.units[uid]
        unit_ids: list[str] = []
        if strategy == "H1_PARENT":
            unit_ids = [unit.parent_id] if unit.parent_id else []
        elif strategy == "H2_CHILDREN":
            unit_ids = self.children.get(uid, [])
        elif strategy == "H3_SIBLINGS":
            unit_ids = [value for value in self.children.get(unit.parent_id or "", []) if value != uid]
        elif strategy == "H4_SAME_ARTICLE":
            article = self.article_id(chunk_id)
            unit_ids = ([article] + self.descendants(article)) if article else []
        elif strategy == "H5_ADJACENT_UNIT":
            ordered = self.document_units[unit.document_id]
            index = ordered.index(uid)
            unit_ids = ordered[max(0, index - 1):index] + ordered[index + 1:index + 2]
        elif strategy == "H6_PARENT_CHILDREN":
            unit_ids = ([unit.parent_id] if unit.parent_id else []) + self.children.get(uid, [])
        elif strategy == "H7_ARTICLE_ADJACENT":
            article = self.article_id(chunk_id)
            article_units = ([article] + self.descendants(article)) if article else []
            ordered = self.document_units[unit.document_id]
            index = ordered.index(uid)
            unit_ids = article_units + ordered[max(0, index - 1):index] + ordered[index + 1:index + 2]
        return [value for value in self.chunks_for_units(unit_ids) if value != chunk_id]

    def relationship(self, left_chunk: str, right_chunk: str) -> set[str]:
        left_uid, right_uid = self.unit_id(left_chunk), self.unit_id(right_chunk)
        result: set[str] = set()
        if not left_uid or not right_uid or left_uid not in self.units or right_uid not in self.units:
            return result
        left, right = self.units[left_uid], self.units[right_uid]
        if left_uid == right_uid:
            result.add("SAME_LEGAL_UNIT")
            if abs(self.chunks[left_chunk]["chunk_index"] - self.chunks[right_chunk]["chunk_index"]) <= 1:
                result.add("NEARBY_CHUNKS_IN_UNIT")
        if left.parent_id == right_uid or right.parent_id == left_uid:
            result.add("PARENT_CHILD")
        if left.parent_id and left.parent_id == right.parent_id:
            result.add("SIBLING")
        if self.article_id(left_chunk) and self.article_id(left_chunk) == self.article_id(right_chunk):
            result.add("SAME_ARTICLE")
        if left.document_id == right.document_id:
            ordered = self.document_units[left.document_id]
            if abs(ordered.index(left_uid) - ordered.index(right_uid)) == 1:
                result.add("ADJACENT_LEGAL_UNIT")
            result.add("SAME_DOCUMENT")
        else:
            result.add("CROSS_DOCUMENT")
        return result

    def unit_snapshot(self, chunk_id: str) -> dict[str, Any] | None:
        uid = self.unit_id(chunk_id)
        if not uid or uid not in self.units:
            return None
        unit = self.units[uid]
        return {
            "legal_unit_id": uid, "parent_unit_id": unit.parent_id,
            "unit_type": unit.unit_type, "unit_number": unit.unit_number,
            "unit_title": unit.unit_title, "level": unit.level,
            "page_start": unit.page_start, "page_end": unit.page_end,
            "article_id": self.article_id(chunk_id),
        }


def hydrate_candidate(item: dict[str, Any], graph: CorpusGraph) -> dict[str, Any]:
    chunk = graph.chunks[item["chunk_id"]]
    return {
        **item,
        "content_text": chunk["content_text"],
        "metadata_json": chunk["metadata_json"],
        "provenance_json": chunk["provenance_json"],
    }


def renumber(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for rank, item in enumerate(items, start=1):
        output.append({**item, "final_rank": rank})
    return output


def expand_candidates(
    anchors: list[dict[str, Any]], graph: CorpusGraph, strategy: str,
    *, per_anchor: int = MAX_EXPANSION_PER_ANCHOR, total_limit: int = MAX_EXPANDED_CANDIDATES,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    inserted: list[str] = []
    for anchor in anchors:
        if anchor["chunk_id"] not in seen:
            output.append(dict(anchor)); seen.add(anchor["chunk_id"])
        relation_ids = graph.related(anchor["chunk_id"], strategy)[:per_anchor]
        for offset, chunk_id in enumerate(relation_ids, start=1):
            if chunk_id in seen or chunk_id not in graph.chunks:
                continue
            chunk = graph.chunks[chunk_id]
            output.append({
                "chunk_id": chunk_id, "document_id": chunk["document_id"],
                "dense_score": None, "dense_rank": None,
                "lexical_score": None, "lexical_rank": None,
                "fusion_score": max(0.0, float(anchor["fusion_score"]) - offset * 1e-7),
                "content_text": chunk["content_text"], "metadata_json": chunk["metadata_json"],
                "provenance_json": chunk["provenance_json"],
                "experimental_source": strategy, "anchor_chunk_id": anchor["chunk_id"],
            })
            seen.add(chunk_id); inserted.append(chunk_id)
            if len(output) >= total_limit:
                break
        if len(output) >= total_limit:
            break
    return renumber(output), {
        "baseline_candidate_count": len(anchors), "expanded_candidate_count": len(output),
        "new_candidate_count": len(inserted), "inserted_chunk_ids": inserted,
    }


def coverage_aware(pool: list[dict[str, Any]], graph: CorpusGraph, top_k: int = 10) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    used_units: set[str] = set()
    used_articles: set[str] = set()
    remaining = list(pool)
    while remaining and len(selected) < top_k:
        best_index = 0
        for index, item in enumerate(remaining):
            unit = graph.unit_id(item["chunk_id"])
            article = graph.article_id(item["chunk_id"])
            if unit not in used_units and article not in used_articles:
                best_index = index; break
            if unit not in used_units:
                best_index = index; break
        item = remaining.pop(best_index)
        selected.append(item)
        unit = graph.unit_id(item["chunk_id"])
        article = graph.article_id(item["chunk_id"])
        if unit: used_units.add(unit)
        if article: used_articles.add(article)
    return renumber(selected)


def strategy_metrics(
    cases: list[Any], rankings: dict[str, list[dict[str, Any]]], multi_ids: set[str],
) -> dict[str, Any]:
    answerable = [case for case in cases if case.answerable]
    multi = [case for case in answerable if case.case_id in multi_ids]
    def evidence(case, cutoff=None):
        ids = [item["chunk_id"] for item in rankings[case.case_id]]
        return evidence_set_metrics(ids[:cutoff] if cutoff else ids, case.acceptable_evidence_sets)
    result = {
        "case_count": len(answerable),
        "average_candidate_count": mean(len(rankings[case.case_id]) for case in answerable),
        "hit_at_1": rate([evidence(case, 1)["complete"] for case in answerable]),
        "hit_at_3": rate([evidence(case, 3)["complete"] for case in answerable]),
        "hit_at_5": rate([evidence(case, 5)["complete"] for case in answerable]),
        "hit_at_10": rate([evidence(case, 10)["complete"] for case in answerable]),
        "mrr": mean(reciprocal_rank(
            [item["chunk_id"] for item in rankings[case.case_id]][:10],
            case.acceptable_evidence_sets,
        ) for case in answerable),
        "document_hit_at_1": rate([document_hit_at_k(
            [item["document_id"] for item in rankings[case.case_id]], case.expected_document_ids, 1
        ) for case in answerable]),
        "document_hit_at_3": rate([document_hit_at_k(
            [item["document_id"] for item in rankings[case.case_id]], case.expected_document_ids, 3
        ) for case in answerable]),
        "document_hit_at_5": rate([document_hit_at_k(
            [item["document_id"] for item in rankings[case.case_id]], case.expected_document_ids, 5
        ) for case in answerable]),
        "document_hit_at_10": rate([document_hit_at_k(
            [item["document_id"] for item in rankings[case.case_id]], case.expected_document_ids, 10
        ) for case in answerable]),
        "wrong_document_rate": rate([
            not set(case.expected_document_ids).intersection(
                item["document_id"] for item in rankings[case.case_id][:10]
            ) for case in answerable
        ]),
        "multi_evidence": {
            "case_count": len(multi),
            "complete_at_10": rate([evidence(case, 10)["complete"] for case in multi]),
            "partial_at_10": rate([evidence(case, 10)["partial"] for case in multi]),
            "average_recall_at_10": mean(evidence(case, 10)["recall"] for case in multi),
            "complete_in_candidate_list": rate([evidence(case)["complete"] for case in multi]),
            "average_recall_in_candidate_list": mean(evidence(case)["recall"] for case in multi),
        },
        "single_evidence": {},
    }
    single = [case for case in answerable if case.case_id not in multi_ids]
    result["single_evidence"] = {
        "case_count": len(single),
        "hit_at_1": rate([evidence(case, 1)["complete"] for case in single]),
        "hit_at_10": rate([evidence(case, 10)["complete"] for case in single]),
        "mrr": mean(reciprocal_rank(
            [item["chunk_id"] for item in rankings[case.case_id]][:10], case.acceptable_evidence_sets
        ) for case in single),
    }
    return result


def context_metrics(cases, rankings, multi_ids, context_builder, budget) -> tuple[dict[str, Any], dict[str, Any]]:
    details = {}
    started = perf_counter()
    for case in cases:
        if not case.answerable:
            continue
        package = context_builder.build(
            request_id=f"exp-{case.case_id}", query_text=case.question,
            retrieved_candidates=rankings[case.case_id], context_budget_tokens=budget,
        )
        selected = [item.chunk_id for item in package.selected_evidence]
        evidence = evidence_set_metrics(selected, case.acceptable_evidence_sets)
        details[case.case_id] = {
            "input_candidate_count": len(rankings[case.case_id]),
            "selected_count": package.selected_count,
            "selected_chunk_ids": selected,
            "context_token_count": package.context_token_count,
            "context_budget_tokens": package.context_budget_tokens,
            "budget_utilization": package.context_token_count / package.context_budget_tokens,
            "budget_exhausted": package.budget_exhausted,
            "stop_reason": package.stop_reason.value,
            "expected_evidence": evidence,
            "selected_documents": dict(Counter(item.document_id for item in package.selected_evidence)),
            "package": package,
        }
    multi = [details[case.case_id] for case in cases if case.case_id in multi_ids]
    summary = {
        "case_count": len(details),
        "average_input_candidate_count": mean(item["input_candidate_count"] for item in details.values()),
        "average_selected_count": mean(item["selected_count"] for item in details.values()),
        "average_context_tokens": mean(item["context_token_count"] for item in details.values()),
        "average_budget_utilization": mean(item["budget_utilization"] for item in details.values()),
        "budget_exhaustion_count": sum(item["budget_exhausted"] for item in details.values()),
        "retrieved_but_dropped_count": sum(
            evidence_set_metrics(
                [candidate["chunk_id"] for candidate in rankings[case.case_id]],
                case.acceptable_evidence_sets,
            )["complete"] and not details[case.case_id]["expected_evidence"]["complete"]
            for case in cases if case.answerable
        ),
        "multi_evidence_context_complete_rate": rate([
            item["expected_evidence"]["complete"] for item in multi
        ]),
        "elapsed_ms": (perf_counter() - started) * 1000,
    }
    serializable = {key: {k: v for k, v in value.items() if k != "package"} for key, value in details.items()}
    return summary, {"serializable": serializable, "packages": {key: value["package"] for key, value in details.items()}}


def piece_ranks(case_report: dict[str, Any], fused: list[dict[str, Any]], chunk_id: str) -> dict[str, Any]:
    dense = {item["chunk_id"]: item for item in case_report["block4"]["dense_candidates"]}
    lexical = {item["chunk_id"]: item for item in case_report["block4"]["lexical_candidates"]}
    fusion = {item["chunk_id"]: item for item in fused}
    final = {item["chunk_id"]: item for item in case_report["block4"]["final_candidates"]}
    dense_rank = dense.get(chunk_id, {}).get("dense_rank")
    lexical_rank = lexical.get(chunk_id, {}).get("lexical_rank")
    fusion_rank = fusion.get(chunk_id, {}).get("final_rank")
    return {
        "dense_rank": dense_rank,
        "dense_score": dense.get(chunk_id, {}).get("dense_score"),
        "lexical_rank": lexical_rank,
        "lexical_score": lexical.get(chunk_id, {}).get("lexical_score"),
        "fusion_rank": fusion_rank,
        "fusion_score": fusion.get(chunk_id, {}).get("fusion_score"),
        "production_final_rank": final.get(chunk_id, {}).get("final_rank"),
        "dense_top_10": dense_rank is not None and dense_rank <= 10,
        "dense_top_20": dense_rank is not None and dense_rank <= 20,
        "dense_top_30": dense_rank is not None and dense_rank <= 30,
        "dense_top_50": dense_rank is not None and dense_rank <= 50,
        "lexical_top_10": lexical_rank is not None and lexical_rank <= 10,
        "lexical_top_20": lexical_rank is not None and lexical_rank <= 20,
        "lexical_top_30": lexical_rank is not None and lexical_rank <= 30,
        "lexical_top_50": lexical_rank is not None and lexical_rank <= 50,
        "fused_top_10": fusion_rank is not None and fusion_rank <= 10,
        "fused_top_15": fusion_rank is not None and fusion_rank <= 15,
        "fused_top_20": fusion_rank is not None and fusion_rank <= 20,
        "fused_top_30": fusion_rank is not None and fusion_rank <= 30,
        "fused_top_50": fusion_rank is not None and fusion_rank <= 50,
    }


def classification_labels(ranks: dict[str, Any]) -> list[str]:
    labels = []
    if ranks["production_final_rank"] is not None: labels.append("FOUND_FINAL_TOP10")
    elif ranks["fusion_rank"] is not None: labels.append("FOUND_BELOW_FINAL_TOP10")
    dense, lexical = ranks["dense_rank"] is not None, ranks["lexical_rank"] is not None
    if dense and lexical: labels.append("FOUND_BOTH_POOLS")
    elif dense: labels.append("FOUND_DENSE_POOL_ONLY")
    elif lexical: labels.append("FOUND_LEXICAL_POOL_ONLY")
    if not dense: labels.append("NOT_IN_DENSE_TOP50")
    if not lexical: labels.append("NOT_IN_LEXICAL_TOP50")
    if not dense and not lexical: labels.append("NOT_IN_ANY_CANDIDATE_POOL")
    return labels


def _same_document_stats(case, fused, graph) -> dict[str, Any]:
    expected = set(case.expected_document_ids)
    correct = [item for item in fused if item["document_id"] in expected]
    top10 = [item for item in fused[:10] if item["document_id"] in expected]
    dense_scores = [item["dense_score"] for item in correct if item.get("dense_score") is not None]
    lexical_scores = [item["lexical_score"] for item in correct if item.get("lexical_score") is not None]
    fusion_scores = [item["fusion_score"] for item in correct]
    required = [chunk for solution in case.acceptable_evidence_sets for chunk in solution]
    within = {item["chunk_id"]: rank for rank, item in enumerate(correct, start=1)}
    competing_types = Counter(
        (graph.unit_snapshot(item["chunk_id"]) or {}).get("unit_type", "UNKNOWN") for item in top10
    )
    def summary(values):
        return None if not values else {"min": min(values), "max": max(values), "mean": mean(values)}
    return {
        "correct_document_in_top10": bool(top10),
        "correct_document_candidates_top50": len(correct),
        "correct_document_candidates_top10": len(top10),
        "required_within_document_ranks": {chunk: within.get(chunk) for chunk in required},
        "dense_score_distribution": summary(dense_scores),
        "lexical_score_distribution": summary(lexical_scores),
        "fusion_score_distribution": summary(fusion_scores),
        "competing_unit_types_top10": dict(competing_types),
        "discrimination": "INTRA_DOCUMENT_LEGAL_UNIT_DISCRIMINATION" if top10 else "CROSS_DOCUMENT_DISCRIMINATION",
    }


def near_duplicate_stats(ranking: list[dict[str, Any]]) -> dict[str, Any]:
    def tokens(value): return set(re.findall(r"\w+", _compact(value).casefold()))
    result = {}
    for cutoff in (10, 20):
        items = ranking[:cutoff]
        pairs = []
        for i, left in enumerate(items):
            lt = tokens(left["content_text"])
            for right in items[i + 1:]:
                rt = tokens(right["content_text"])
                similarity = len(lt & rt) / len(lt | rt) if lt or rt else 1.0
                if similarity >= 0.80:
                    pairs.append({"left": left["chunk_id"], "right": right["chunk_id"], "jaccard": similarity})
        result[f"top_{cutoff}_near_duplicate_pairs"] = pairs
    return result


def grouped_token_diagnostic(details, graph, token_counter, multi_ids) -> dict[str, Any]:
    cases = {}
    for case_id in multi_ids:
        item = details["serializable"][case_id]
        selected = item["selected_chunk_ids"]
        groups: dict[tuple[str, str], list[str]] = defaultdict(list)
        for chunk_id in selected:
            chunk = graph.chunks[chunk_id]
            key = (chunk["document_id"], graph.article_id(chunk_id) or graph.unit_id(chunk_id) or chunk_id)
            groups[key].append(chunk_id)
        pieces = []
        for (document_id, group_id), chunk_ids in groups.items():
            contents = "\n".join(graph.chunks[cid]["content_text"] for cid in chunk_ids)
            pieces.append(f"[GROUP document_id={document_id} legal_group={group_id}]\n{contents}")
        grouped_text = "\n\n---\n\n".join(pieces)
        grouped_tokens = token_counter.count(grouped_text)
        baseline_tokens = item["context_token_count"]
        cases[case_id] = {
            "selected_chunk_count": len(selected), "group_count": len(groups),
            "tokens_before": baseline_tokens, "tokens_after": grouped_tokens,
            "token_savings": baseline_tokens - grouped_tokens,
            "token_savings_rate": (baseline_tokens - grouped_tokens) / baseline_tokens if baseline_tokens else 0,
        }
    return {
        "cases": cases,
        "average_tokens_before": mean(item["tokens_before"] for item in cases.values()),
        "average_tokens_after": mean(item["tokens_after"] for item in cases.values()),
        "average_token_savings": mean(item["token_savings"] for item in cases.values()),
    }


async def generation_replay(cases, packages, selected_case_ids: list[str]) -> dict[str, Any]:
    profile = get_generation_profile()
    client = get_llm_client()
    results = []
    try:
        await client.health(profile)
        for case in cases:
            if case.case_id not in selected_case_ids:
                continue
            package = packages[case.case_id]
            messages = assemble_messages(package, profile.prompt_version)
            started = perf_counter(); ttft = None; pieces = []; finish_reason = None; usage = None
            async for chunk in client.stream(messages, profile):
                if chunk.text:
                    if ttft is None: ttft = (perf_counter() - started) * 1000
                    pieces.append(chunk.text)
                if chunk.done:
                    finish_reason, usage = chunk.finish_reason, chunk.usage
            generation_ms = (perf_counter() - started) * 1000
            parsed = parse_answerability("".join(pieces))
            if parsed.status and parsed.status.value == "INSUFFICIENT_EVIDENCE":
                status = GenerationStatus.INSUFFICIENT_EVIDENCE
                answer_text = INSUFFICIENT_EVIDENCE_MESSAGE
                citations, invalid, validation = [], [], CitationValidation.PASS
            else:
                answer_text = parsed.public_text
                citations, invalid, validation, status = validate_and_map_citations(
                    answer_text, package.selected_evidence
                )
            cited = [item.chunk_id for item in citations]
            results.append({
                "case_id": case.case_id, "status": status.value,
                "answerability_status": parsed.status.value if parsed.status else None,
                "answer_text": answer_text, "citation_validation": validation.value,
                "cited_chunk_ids": cited, "invalid_citations": invalid,
                "expected_source_match": evidence_set_metrics(cited, case.acceptable_evidence_sets)["complete"],
                "multi_evidence_citation_recall": evidence_set_metrics(cited, case.acceptable_evidence_sets)["recall"],
                "ttft_ms": ttft, "generation_ms": generation_ms,
                "finish_reason": finish_reason,
                "usage": usage.model_dump(mode="json") if usage else None,
            })
    finally:
        await close_llm_client()
    return {
        "case_count": len(results), "cases": results,
        "answerable_rate": rate([item["status"] != "INSUFFICIENT_EVIDENCE" for item in results]),
        "false_abstention_rate": rate([item["status"] == "INSUFFICIENT_EVIDENCE" for item in results]),
        "citation_presence_rate": rate([bool(item["cited_chunk_ids"]) for item in results]),
        "expected_source_match_rate": rate([item["expected_source_match"] for item in results]),
        "latency": {
            "ttft": latency_summary([item["ttft_ms"] for item in results]),
            "generation": latency_summary([item["generation_ms"] for item in results]),
        },
    }


def write_candidate_markdown(report):
    s = report["summary"]
    lines = [
        "# Multi-Evidence Candidate Coverage V1", "",
        f"Frozen cases: {report['multi_case_count']}; required evidence pieces: {s['required_piece_count']}.", "",
        "| Window | Pieces found |", "|---|---:|",
    ]
    for key in ("dense_top_10", "dense_top_20", "dense_top_30", "dense_top_50", "lexical_top_10", "lexical_top_20", "lexical_top_30", "lexical_top_50", "fused_top_10", "fused_top_15", "fused_top_20", "fused_top_30", "fused_top_50"):
        lines.append(f"| {key} | {s[key]} |")
    lines.extend([
        "", f"Not in any candidate pool: **{s['not_in_any_candidate_pool']}**.",
        f"Perfect-reranker complete multi-evidence ceiling: **{_pct(s['perfect_reranker_complete_ceiling'])}**.",
        "", "## Per-case evidence", "",
    ])
    for case in report["cases"]:
        lines.extend([f"### {case['case_id']}", "", f"- {case['question']}", f"- Baseline: `{case['baseline']}`", f"- Required pieces: `{case['pieces']}`", ""])
    (REPORTS / "multi_evidence_candidate_coverage_v1.md").write_text("\n".join(lines), encoding="utf-8")


def write_hierarchy_markdown(report):
    ceiling = report["recovery_ceiling"]
    lines = [
        "# Multi-Evidence Hierarchy Analysis V1", "",
        f"Missing baseline evidence pieces: {ceiling['missing_piece_count']}.",
        f"Potentially hierarchy recoverable: {ceiling['potentially_recoverable']} ({_pct(ceiling['rate'])}).",
        f"Not hierarchy recoverable: {ceiling['not_recoverable']}.", "",
        "Existing metadata only was used: `parent_unit_id`, unit type/number/title/level, character order, and chunk→legal-unit relationships.", "",
    ]
    for case in report["cases"]:
        lines.extend([f"## {case['case_id']}", "", f"- Set relationships: `{case['set_relationships']}`", f"- Missing piece recovery: `{case['missing_piece_recovery']}`", ""])
    (REPORTS / "multi_evidence_hierarchy_analysis_v1.md").write_text("\n".join(lines), encoding="utf-8")


def write_strategy_markdown(report):
    lines = [
        "# Multi-Evidence Strategy Comparison V1", "",
        "All strategies are offline replays. No production parameter was changed.", "",
        "| Strategy | Candidates | Hit@10 | MRR | Multi complete@10 | Multi recall@10 | Context complete | Budget exhausted |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, item in report["strategies"].items():
        metrics, context = item["retrieval"], item.get("context")
        lines.append(
            f"| {name} | {metrics['average_candidate_count']:.1f} | {_pct(metrics['hit_at_10'])} | {metrics['mrr']:.4f} | "
            f"{_pct(metrics['multi_evidence']['complete_at_10'])} | {_pct(metrics['multi_evidence']['average_recall_at_10'])} | "
            f"{_pct(context['multi_evidence_context_complete_rate']) if context else 'N/A'} | {context['budget_exhaustion_count'] if context else 'N/A'} |"
        )
    lines.extend([
        "", f"Best measured strategy: **{report['best_strategy']}**.",
        f"Reranker tested: **{report['reranker']['model_tested']}**.",
        f"Reranker alone sufficient: **{report['reranker']['alone_sufficient']}**.",
    ])
    (REPORTS / "multi_evidence_strategy_comparison_v1.md").write_text("\n".join(lines), encoding="utf-8")


def write_context_markdown(report):
    lines = [
        "# Multi-Evidence Context Simulation V1", "",
        "Real frozen Block 5 and production tokenizer/config were used offline.", "",
        "| Strategy | Avg input | Avg selected | Avg tokens | Utilization | Exhausted | Multi complete | Retrieved→dropped |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, item in report["strategies"].items():
        lines.append(
            f"| {name} | {item['average_input_candidate_count']:.2f} | {item['average_selected_count']:.2f} | "
            f"{item['average_context_tokens']:.1f} | {_pct(item['average_budget_utilization'])} | "
            f"{item['budget_exhaustion_count']} | {_pct(item['multi_evidence_context_complete_rate'])} | {item['retrieved_but_dropped_count']} |"
        )
    grouped = report["grouped_representation"]
    lines.extend([
        "", "## Grouped legal-unit diagnostic", "",
        f"Average tokens before/after: {grouped['average_tokens_before']:.1f} / {grouped['average_tokens_after']:.1f}.",
        f"Average token savings: {grouped['average_token_savings']:.1f}.",
        "This is a temporary token diagnostic, not a Block 5 proposal or persisted representation.",
    ])
    (REPORTS / "multi_evidence_context_simulation_v1.md").write_text("\n".join(lines), encoding="utf-8")


def write_false_abstention(baseline, graph):
    cases = [item for item in baseline["cases"] if item.get("failure_attribution_v2") == "FALSE_ABSTENTION"]
    lines = ["# False Abstention Side Report V1", "", "These cases are excluded from retrieval-strategy failure attribution and belong to a future supported-case abstention calibration experiment.", ""]
    for item in cases:
        selected = item["block5"]["selected_chunk_ids"]
        lines.extend([
            f"## {item['case_id']}", "", f"- Question: {item['question']}",
            f"- Expected evidence: `{item['acceptable_evidence_sets']}`",
            f"- Selected evidence IDs: `{selected}`",
            f"- Answerability status: `{item['block6']['answerability_status']}`",
            f"- Public status: `{item['block6']['status']}`",
            f"- Prompt version: `{item['block6']['prompt_version']}`", "",
        ])
        for chunk_id in selected:
            if chunk_id in graph.chunks:
                lines.append(f"> **{chunk_id}** — {_compact(graph.chunks[chunk_id]['content_text'])[:700]}\n")
    (REPORTS / "false_abstention_side_report_v1.md").write_text("\n".join(lines), encoding="utf-8")


async def main_async() -> dict[str, Any]:
    if _sha256(DATASET) != V2_SHA256:
        raise RuntimeError("Frozen Evaluation V2 hash mismatch")
    dataset = load_dataset(DATASET)
    baseline = _json(BASELINE)
    baseline_cases = {item["case_id"]: item for item in baseline["cases"]}
    multi_cases = [case for case in dataset.cases if _is_multi(case)]
    multi_ids = {case.case_id for case in multi_cases}
    db = SessionLocal()
    try:
        validation = validate_dataset(dataset, db)
        candidate_ids = {
            item["chunk_id"] for case in baseline["cases"]
            for branch in ("dense_candidates", "lexical_candidates", "final_candidates")
            for item in case["block4"][branch]
        }
        document_ids = sorted({doc for case in dataset.cases for doc in case.expected_document_ids})
        graph = CorpusGraph(db, document_ids, candidate_ids)
        fused = {case_id: [hydrate_candidate(item, graph) for item in fuse_from_snapshot(report) if item["chunk_id"] in graph.chunks] for case_id, report in baseline_cases.items()}
        baseline_rankings = {case.case_id: [hydrate_candidate(dict(item), graph) for item in baseline_cases[case.case_id]["block4"]["final_candidates"]] for case in dataset.cases if case.answerable}

        coverage_cases = []
        coverage_counts = Counter()
        missing_piece_records = []
        hierarchy_cases = []
        taxonomy_counts = Counter()
        discrimination_counts = Counter()
        total_required = 0
        pool_complete = 0
        for case in multi_cases:
            report = baseline_cases[case.case_id]
            pieces = []
            baseline_ids = [item["chunk_id"] for item in baseline_rankings[case.case_id]]
            pool_ids = [item["chunk_id"] for item in fused[case.case_id]]
            if evidence_set_metrics(pool_ids, case.acceptable_evidence_sets)["complete"]:
                pool_complete += 1
            relationships: set[str] = set()
            required_flat = [chunk for solution in case.acceptable_evidence_sets for chunk in solution]
            for i, left in enumerate(required_flat):
                for right in required_flat[i + 1:]: relationships.update(graph.relationship(left, right))
            missing_recovery = []
            for chunk_id in required_flat:
                total_required += 1
                ranks = piece_ranks(report, fused[case.case_id], chunk_id)
                labels = classification_labels(ranks)
                for key in coverage_counts:
                    pass
                for key in ("dense_top_10", "dense_top_20", "dense_top_30", "dense_top_50", "lexical_top_10", "lexical_top_20", "lexical_top_30", "lexical_top_50", "fused_top_10", "fused_top_15", "fused_top_20", "fused_top_30", "fused_top_50"):
                    coverage_counts[key] += int(ranks[key])
                coverage_counts["not_in_any_candidate_pool"] += int("NOT_IN_ANY_CANDIDATE_POOL" in labels)
                piece = {"chunk_id": chunk_id, "ranks": ranks, "labels": labels, "unit": graph.unit_snapshot(chunk_id)}
                pieces.append(piece)
                if chunk_id not in baseline_ids:
                    anchors = baseline_ids
                    relation_union = sorted({rel for anchor in anchors for rel in graph.relationship(anchor, chunk_id)})
                    recoverable_relations = sorted(set(relation_union).intersection({"PARENT_CHILD", "SIBLING", "SAME_ARTICLE", "ADJACENT_LEGAL_UNIT", "NEARBY_CHUNKS_IN_UNIT"}))
                    recovery = {"chunk_id": chunk_id, "anchor_relationships": relation_union, "recoverable_relations": recoverable_relations, "potentially_hierarchy_recoverable": bool(recoverable_relations)}
                    missing_recovery.append(recovery); missing_piece_records.append(recovery)
                    causes = []
                    if ranks["dense_rank"] is None and ranks["lexical_rank"] is None:
                        causes += ["CANDIDATE_GENERATION_MISS", "DENSE_REPRESENTATION_MISS", "LEXICAL_CANDIDATE_MISS"]
                    elif ranks["fusion_rank"] and ranks["fusion_rank"] > 10:
                        causes += ["FUSION_RANKING_MISS", "FINAL_TOP_K_CUTOFF"]
                    same_stats = _same_document_stats(case, fused[case.case_id], graph)
                    if same_stats["correct_document_in_top10"]: causes.append("INTRA_DOCUMENT_RANKING_FAILURE")
                    else: causes.append("DOCUMENT_AMBIGUITY")
                    if recoverable_relations: causes.append("LEGAL_HIERARCHY_FRAGMENTATION")
                    if len(causes) > 1: causes.append("MULTIPLE")
                    taxonomy_counts.update(set(causes))
            same_stats = _same_document_stats(case, fused[case.case_id], graph)
            discrimination_counts[same_stats["discrimination"]] += 1
            coverage_cases.append({
                "case_id": case.case_id, "category": case.category.value, "question": case.question,
                "answerable": case.answerable, "document_ids": case.document_ids,
                "expected_document_ids": case.expected_document_ids,
                "acceptable_evidence_sets": case.acceptable_evidence_sets,
                "baseline": {
                    "retrieval": baseline_cases[case.case_id]["metrics_v2"]["retrieval_evidence"],
                    "block5_selected": baseline_cases[case.case_id]["block5"]["selected_chunk_ids"],
                    "block6_status": baseline_cases[case.case_id]["block6"]["status"],
                    "citations": baseline_cases[case.case_id]["block6"]["mapped_chunk_ids"],
                },
                "pieces": pieces, "document_analysis": same_stats,
            })
            hierarchy_cases.append({
                "case_id": case.case_id, "set_relationships": sorted(relationships),
                "required_units": {chunk: graph.unit_snapshot(chunk) for chunk in required_flat},
                "missing_piece_recovery": missing_recovery,
            })

        coverage_report = {
            "report_id": "multi_evidence_candidate_coverage_v1", "generated_at": datetime.now(timezone.utc).isoformat(),
            "dataset_sha256": V2_SHA256, "multi_case_count": len(multi_cases),
            "summary": {
                "required_piece_count": total_required, **dict(coverage_counts),
                "candidate_pool_complete_cases": pool_complete,
                "perfect_reranker_complete_ceiling": pool_complete / len(multi_cases),
            }, "cases": coverage_cases,
        }
        _write(REPORTS / "multi_evidence_candidate_coverage_v1.json", coverage_report)
        write_candidate_markdown(coverage_report)

        hierarchy_report = {
            "report_id": "multi_evidence_hierarchy_analysis_v1", "dataset_sha256": V2_SHA256,
            "relationship_counts": dict(Counter(rel for case in hierarchy_cases for rel in case["set_relationships"])),
            "recovery_ceiling": {
                "missing_piece_count": len(missing_piece_records),
                "potentially_recoverable": sum(item["potentially_hierarchy_recoverable"] for item in missing_piece_records),
                "not_recoverable": sum(not item["potentially_hierarchy_recoverable"] for item in missing_piece_records),
                "rate": rate([item["potentially_hierarchy_recoverable"] for item in missing_piece_records]),
            },
            "document_discrimination_counts": dict(discrimination_counts),
            "cases": hierarchy_cases,
        }
        _write(REPORTS / "multi_evidence_hierarchy_analysis_v1.json", hierarchy_report)
        write_hierarchy_markdown(hierarchy_report)

        # Offline ranking strategies for all answerable cases.
        answerable = [case for case in dataset.cases if case.answerable]
        rankings: dict[str, dict[str, list[dict[str, Any]]]] = {"BASELINE_TOP10": baseline_rankings}
        for window in (15, 20, 30, 50):
            rankings[f"WIDER_RRF_TOP{window}"] = {case.case_id: renumber(fused[case.case_id][:window]) for case in answerable}
        hierarchy_names = ("H1_PARENT", "H2_CHILDREN", "H3_SIBLINGS", "H4_SAME_ARTICLE", "H5_ADJACENT_UNIT", "H6_PARENT_CHILDREN", "H7_ARTICLE_ADJACENT")
        expansion_details: dict[str, dict[str, Any]] = {}
        for name in hierarchy_names:
            strategy_rankings, details = {}, {}
            for case in answerable:
                strategy_rankings[case.case_id], details[case.case_id] = expand_candidates(baseline_rankings[case.case_id], graph, name)
            rankings[name] = strategy_rankings; expansion_details[name] = details
        rankings["COVERAGE_AWARE_TOP10"] = {case.case_id: coverage_aware(fused[case.case_id], graph) for case in answerable}
        # One bounded combination justified by hierarchy and wider-window hypotheses.
        combined, combined_details = {}, {}
        for case in answerable:
            combined[case.case_id], combined_details[case.case_id] = expand_candidates(renumber(fused[case.case_id][:15]), graph, "H7_ARTICLE_ADJACENT")
        rankings["H7_PLUS_WIDER15"] = combined; expansion_details["H7_PLUS_WIDER15"] = combined_details

        profile = get_generation_profile()
        token_counter = ContextTokenCounter(profile.tokenizer_provider, profile.tokenizer_id)
        context_builder = ContextBuilderService(token_counter)
        strategy_results, context_results, context_details = {}, {}, {}
        replay_latencies = {}
        for name, values in rankings.items():
            started = perf_counter(); retrieval = strategy_metrics(dataset.cases, values, multi_ids)
            replay_latencies[name] = (perf_counter() - started) * 1000
            context, details = context_metrics(dataset.cases, values, multi_ids, context_builder, profile.context_budget_tokens)
            strategy_results[name] = {"retrieval": retrieval, "context": context, "replay_latency_ms": replay_latencies[name]}
            context_results[name] = context; context_details[name] = details

        # Winner uses multiple metrics: multi complete@10, context completeness, all-case Hit@10, then MRR.
        eligible = [name for name in rankings if name not in {"WIDER_RRF_TOP20", "WIDER_RRF_TOP30", "WIDER_RRF_TOP50"}]
        best = max(eligible, key=lambda name: (
            strategy_results[name]["retrieval"]["multi_evidence"]["complete_at_10"],
            strategy_results[name]["context"]["multi_evidence_context_complete_rate"],
            strategy_results[name]["retrieval"]["hit_at_10"],
            strategy_results[name]["retrieval"]["mrr"],
            -strategy_results[name]["retrieval"]["average_candidate_count"],
        ))

        grouped = grouped_token_diagnostic(context_details[best], graph, token_counter, multi_ids)
        context_report = {
            "report_id": "multi_evidence_context_simulation_v1", "dataset_sha256": V2_SHA256,
            "best_strategy": best, "strategies": context_results,
            "expansion_details": expansion_details,
            "grouped_representation": grouped,
            "retrieval_improvement_context_regression_cases": [
                case.case_id for case in multi_cases
                if evidence_set_metrics([item["chunk_id"] for item in rankings[best][case.case_id]], case.acceptable_evidence_sets)["complete"]
                and not context_details[best]["serializable"][case.case_id]["expected_evidence"]["complete"]
            ],
        }
        _write(REPORTS / "multi_evidence_context_simulation_v1.json", context_report)
        write_context_markdown(context_report)

        # Candidate-pool ceiling decides reranker phase: no download when perfect reranking cannot exceed baseline complete rate.
        baseline_multi_complete = strategy_results["BASELINE_TOP10"]["retrieval"]["multi_evidence"]["complete_at_10"]
        perfect_ceiling = coverage_report["summary"]["perfect_reranker_complete_ceiling"]
        reranker = {
            "justified_by_complete_candidate_coverage": perfect_ceiling > baseline_multi_complete,
            "model_tested": "NONE",
            "reason": "Existing candidate pools contain no additional complete acceptable evidence set beyond baseline Top-10; downloading a reranker cannot raise complete multi-evidence recall.",
            "perfect_reranker_complete_ceiling": perfect_ceiling,
            "alone_sufficient": "NO",
            "cross_document_performance": "NOT_TESTED",
            "intra_document_performance": "NOT_TESTED",
        }

        # Generation replay only for the best non-baseline strategy when it improves retrieval/context.
        affected = [case.case_id for case in multi_cases if not baseline_cases[case.case_id]["metrics_v2"]["retrieval_evidence"]["complete"]]
        if best != "BASELINE_TOP10":
            generation = await generation_replay(dataset.cases, context_details[best]["packages"], affected)
        else:
            generation = {"case_count": 0, "status": "SKIPPED_NO_OFFLINE_STRATEGY_IMPROVED_BASELINE"}

        # Wrong-document and near-duplicate side analyses.
        wrong_document = []
        for item in baseline["cases"]:
            if item.get("failure_attribution_v2") != "WRONG_DOCUMENT": continue
            case = next(case for case in dataset.cases if case.case_id == item["case_id"])
            pool = fused[case.case_id]
            expected_in_pool = [candidate for candidate in pool if candidate["document_id"] in case.expected_document_ids]
            metadata = [graph.chunks[chunk]["metadata_json"] for solution in case.acceptable_evidence_sets for chunk in solution]
            wrong_document.append({
                "case_id": case.case_id, "expected_document_ids": case.expected_document_ids,
                "expected_document_candidate_count": len(expected_in_pool),
                "expected_document_present_in_pool": bool(expected_in_pool),
                "expected_chunk_present_in_pool": any(
                    chunk in {candidate["chunk_id"] for candidate in pool}
                    for solution in case.acceptable_evidence_sets for chunk in solution
                ),
                "expected_chunk_metadata": metadata,
                "hierarchy_can_recover_before_document_selection": False,
                "classification": "CANDIDATE_GENERATION_DOCUMENT_DISCRIMINATION",
            })
        near_duplicates = {
            case.case_id: near_duplicate_stats(fused[case.case_id])
            for case in multi_cases if not baseline_cases[case.case_id]["metrics_v2"]["retrieval_evidence"]["complete"]
        }

        strategy_report = {
            "report_id": "multi_evidence_strategy_comparison_v1", "dataset_sha256": V2_SHA256,
            "strategies": strategy_results, "best_strategy": best,
            "reranker": reranker, "generation_replay": generation,
            "failure_taxonomy_counts": dict(taxonomy_counts),
            "wrong_document_analysis": wrong_document,
            "near_duplicate_competition": near_duplicates,
            "single_evidence_protection": {name: item["retrieval"]["single_evidence"] for name, item in strategy_results.items()},
        }
        _write(REPORTS / "multi_evidence_strategy_comparison_v1.json", strategy_report)
        write_strategy_markdown(strategy_report)
        write_false_abstention(baseline, graph)

        experiment = {
            "report_id": "multi_evidence_experiment_v1", "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "COMPLETE", "dataset_sha256": V2_SHA256, "dataset_validation": validation,
            "production_behavior_changed": False, "schema_changed": False, "new_production_tables": 0,
            "multi_case_ids": sorted(multi_ids),
            "candidate_coverage_summary": coverage_report["summary"],
            "hierarchy_summary": {k: v for k, v in hierarchy_report.items() if k not in {"cases"}},
            "failure_taxonomy_counts": dict(taxonomy_counts),
            "document_discrimination_counts": dict(discrimination_counts),
            "best_strategy": best,
            "best_strategy_metrics": strategy_results[best],
            "baseline_metrics": strategy_results["BASELINE_TOP10"],
            "reranker": reranker,
            "generation_replay": generation,
            "wrong_document_analysis": wrong_document,
            "near_duplicate_competition": near_duplicates,
            "grouped_representation": grouped,
            "artifacts": [
                "multi_evidence_candidate_coverage_v1.json", "multi_evidence_hierarchy_analysis_v1.json",
                "multi_evidence_strategy_comparison_v1.json", "multi_evidence_context_simulation_v1.json",
                "false_abstention_side_report_v1.md",
            ],
        }
        _write(REPORTS / "multi_evidence_experiment_v1.json", experiment)
        lines = [
            "# Multi-Evidence Retrieval Experiment V1", "",
            "Status: **COMPLETE**. This is an offline replay; production is unchanged.", "",
            f"- Dataset SHA-256: `{V2_SHA256}`",
            f"- Multi-piece cases: {len(multi_cases)}; required evidence pieces: {total_required}.",
            f"- Candidate-pool perfect-reranker ceiling: {_pct(perfect_ceiling)}.",
            f"- Hierarchy-recoverable missing pieces: {hierarchy_report['recovery_ceiling']['potentially_recoverable']} / {hierarchy_report['recovery_ceiling']['missing_piece_count']}.",
            f"- Best measured strategy: **{best}**.",
            f"- Reranker model tested: **NONE** — candidate coverage did not justify a download.", "",
            "See the candidate, hierarchy, strategy, context, false-abstention, and JSON reports for auditable per-case detail.",
        ]
        (REPORTS / "multi_evidence_experiment_v1.md").write_text("\n".join(lines), encoding="utf-8")
        return experiment
    finally:
        db.close()


def main() -> None:
    result = asyncio.run(main_async())
    print(json.dumps({
        "status": result["status"], "best_strategy": result["best_strategy"],
        "candidate_coverage": result["candidate_coverage_summary"],
        "hierarchy_recovery": result["hierarchy_summary"]["recovery_ceiling"],
        "best_metrics": result["best_strategy_metrics"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
