"""Build the deterministic Legal-RAG-V3 human legal-review gate artifacts.

This module does not call an LLM, rerun evaluation, or mutate frozen data. The
authoritative queue is loaded from the existing V3 production-validation
report, then source text and legal-unit lineage are hydrated read-only from the
frozen corpus database.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from email.header import decode_header, make_header
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.db.database import SessionLocal


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "evaluation" / "reports"
SOURCE_REPORT = REPORTS / "legal_rag_v3_production_validation_v1.json"
HIERARCHY_REPORT = REPORTS / "legal_hierarchy_v2_generation.json"
OUTPUT_JSON = REPORTS / "legal_rag_v3_human_legal_review_gate_v1.json"
OUTPUT_MD = REPORTS / "legal_rag_v3_human_legal_review_gate_v1.md"
FORM_MD = REPORTS / "legal_rag_v3_human_review_form_v1.md"

FROZEN = {
    "evaluation_v1": (
        ROOT / "evaluation" / "datasets" / "legal_eval_v1.json",
        "afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245",
    ),
    "evaluation_v2": (
        ROOT / "evaluation" / "datasets" / "legal_eval_v2.json",
        "ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842",
    ),
    "legal_rag_v2": (
        ROOT / "app" / "prompts" / "legal-rag-v2.txt",
        "a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee",
    ),
    "legal_rag_v3": (
        ROOT / "app" / "prompts" / "legal-rag-v3.txt",
        "35b0abd69608ef574ac7bbf5c314eadb6ef9decd0dda3dd60e0a170aad243ebf",
    ),
}

UNEXPECTED_REASON = "STRUCTURALLY_VALID_UNEXPECTED_SOURCE"
QUALIFIED_REASON = "QUALIFIED_PARTIAL_SUPPORT"
GAIN_REASON = "V3_ANSWERABILITY_GAIN"
MULTI_REASON = "MULTI_EVIDENCE_FAILURE"
UNRESOLVED_REASON = "V3_UNRESOLVED_FALSE_ABSTENTION"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact(value: str, limit: int = 220) -> str:
    normalized = " ".join(value.split())
    return normalized if len(normalized) <= limit else normalized[: limit - 1] + "…"


def md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def quoted(value: str) -> str:
    return "> " + value.replace("\n", "\n> ")


def decoded_filename(value: str) -> str:
    try:
        return str(make_header(decode_header(value)))
    except (LookupError, UnicodeError):
        return value


def source_id_map(review_case: dict[str, Any]) -> dict[str, str]:
    return {item["chunk_id"]: item["source_id"] for item in review_case["selected_evidence"]}


def candidate_map(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["chunk_id"]: item for item in case["block4"]["final_candidates"]}


def hydrate_chunks(db, chunk_ids: set[str]) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    if not chunk_ids:
        return {}, {}
    rows = db.execute(text("""
        SELECT c.id, c.document_id, c.legal_unit_id, c.content_text,
               c.page_start, c.page_end, c.metadata_json, c.provenance_json,
               d.filename, d.sha256 AS document_sha256
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.id = ANY(CAST(:chunk_ids AS uuid[]))
    """), {"chunk_ids": sorted(chunk_ids)}).mappings().all()
    chunks = {
        str(row["id"]): {
            "chunk_id": str(row["id"]),
            "document_id": str(row["document_id"]),
            "legal_unit_id": str(row["legal_unit_id"]) if row["legal_unit_id"] else None,
            "content_text": row["content_text"],
            "page_start": row["page_start"],
            "page_end": row["page_end"],
            "metadata_json": row["metadata_json"] or {},
            "provenance_json": row["provenance_json"] or {},
            "filename": decoded_filename(row["filename"]),
            "document_sha256": row["document_sha256"],
        }
        for row in rows
    }
    missing = chunk_ids - set(chunks)
    if missing:
        raise RuntimeError(f"review chunks missing from corpus: {sorted(missing)}")

    lineage_rows = db.execute(text("""
        WITH RECURSIVE lineage AS (
            SELECT c.id AS root_chunk_id, lu.id, lu.parent_unit_id,
                   lu.unit_type, lu.unit_number, lu.unit_title,
                   lu.page_start, lu.page_end, lu.level
            FROM chunks c
            JOIN legal_units lu ON lu.id = c.legal_unit_id
            WHERE c.id = ANY(CAST(:chunk_ids AS uuid[]))
            UNION ALL
            SELECT l.root_chunk_id, parent.id, parent.parent_unit_id,
                   parent.unit_type, parent.unit_number, parent.unit_title,
                   parent.page_start, parent.page_end, parent.level
            FROM lineage l
            JOIN legal_units parent ON parent.id = l.parent_unit_id
        )
        SELECT * FROM lineage ORDER BY root_chunk_id, level
    """), {"chunk_ids": sorted(chunk_ids)}).mappings().all()
    lineage: dict[str, list[dict[str, Any]]] = {}
    for row in lineage_rows:
        lineage.setdefault(str(row["root_chunk_id"]), []).append({
            "legal_unit_id": str(row["id"]),
            "unit_type": row["unit_type"],
            "unit_number": row["unit_number"],
            "unit_title": row["unit_title"],
            "page_start": row["page_start"],
            "page_end": row["page_end"],
            "level": row["level"],
        })
    return chunks, lineage


def locator(units: list[dict[str, Any]]) -> dict[str, Any]:
    def find(kind: str):
        match = next((item for item in units if item["unit_type"] == kind), None)
        if not match:
            return None
        return {
            "number": match["unit_number"],
            "title": match["unit_title"],
            "legal_unit_id": match["legal_unit_id"],
        }

    return {
        "article": find("ARTICLE"),
        "clause": find("CLAUSE"),
        "point": find("POINT"),
        "lineage": units,
    }


def snapshot(
    chunk_id: str,
    *,
    chunks: dict[str, dict[str, Any]],
    lineage: dict[str, list[dict[str, Any]]],
    source_ids: dict[str, str],
    candidates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    chunk = chunks[chunk_id]
    candidate = candidates.get(chunk_id)
    return {
        **chunk,
        "source_id": source_ids.get(chunk_id),
        "legal_locator": locator(lineage.get(chunk_id, [])),
        "selected": chunk_id in source_ids,
        "retrieval_origin": candidate.get("candidate_origin") if candidate else "NOT_IN_FINAL_CONTEXT_CANDIDATES",
        "retrieval_final_rank": candidate.get("retrieval_final_rank") if candidate else None,
        "context_candidate_order": candidate.get("context_candidate_order") if candidate else None,
        "hierarchy_relation": candidate.get("hierarchy_relation") if candidate else None,
        "anchor_chunk_id": candidate.get("anchor_chunk_id") if candidate else None,
    }


def structural_relationship(expected: list[dict[str, Any]], actual: list[dict[str, Any]]) -> dict[str, Any]:
    expected_docs = {item["document_id"] for item in expected}
    actual_docs = {item["document_id"] for item in actual}
    if expected_docs == actual_docs:
        document_relationship = "SAME_DOCUMENT_SET"
    elif expected_docs & actual_docs:
        document_relationship = "OVERLAPPING_DOCUMENT_SET"
    else:
        document_relationship = "DIFFERENT_DOCUMENT_SET"

    def articles(items):
        return {
            (
                item["document_id"],
                (item["legal_locator"].get("article") or {}).get("number"),
            )
            for item in items
            if item["legal_locator"].get("article")
        }

    expected_articles, actual_articles = articles(expected), articles(actual)
    if expected_articles and actual_articles and expected_articles & actual_articles:
        article_relationship = "SAME_ARTICLE_PRESENT"
    elif expected_articles and actual_articles:
        article_relationship = "DIFFERENT_ARTICLES"
    else:
        article_relationship = "ARTICLE_RELATIONSHIP_UNKNOWN"
    return {
        "expected_document_ids": sorted(expected_docs),
        "actual_document_ids": sorted(actual_docs),
        "document_relationship": document_relationship,
        "expected_articles": [list(item) for item in sorted(expected_articles)],
        "actual_articles": [list(item) for item in sorted(actual_articles)],
        "article_clause_relationship": article_relationship,
        "overlapping_legal_proposition": "PENDING_HUMAN_REVIEW",
        "differing_legal_proposition": "PENDING_HUMAN_REVIEW",
        "review_label": "INSUFFICIENT_FOR_AUTOMATIC_DETERMINATION",
        "final_legal_correctness": None,
    }


def answer_segments(answer: str, selected_by_source: dict[str, str], expected_ids: set[str]) -> list[dict[str, Any]]:
    parts = [item.strip() for item in re.split(r"(?<=[.!?])\s+(?=[A-ZĐ])", answer) if item.strip()]
    output = []
    for part in parts:
        source_ids = re.findall(r"\[(S[1-9][0-9]*)\]", part)
        chunk_ids = [selected_by_source[item] for item in source_ids if item in selected_by_source]
        output.append({
            "text": part,
            "citation_source_ids": source_ids,
            "citation_chunk_ids": chunk_ids,
            "citation_scope": (
                "EXPECTED_EVIDENCE_PRESENT" if expected_ids & set(chunk_ids)
                else "ONLY_ADDITIONAL_SELECTED_EVIDENCE" if chunk_ids
                else "NO_STRUCTURED_CITATION"
            ),
            "legal_support_decision": None,
        })
    return output


def build() -> dict[str, Any]:
    integrity = {}
    for key, (path, expected) in FROZEN.items():
        actual = sha256(path)
        integrity[key] = {"path": str(path.relative_to(ROOT)), "expected": expected, "actual": actual, "match": actual == expected}
    if not all(item["match"] for item in integrity.values()):
        raise RuntimeError(f"frozen fingerprint mismatch: {integrity}")

    source = json.loads(SOURCE_REPORT.read_text(encoding="utf-8"))
    hierarchy = json.loads(HIERARCHY_REPORT.read_text(encoding="utf-8"))
    authoritative_queue = source["human_review"]
    if not authoritative_queue:
        raise RuntimeError("authoritative human review queue is empty")
    hierarchy_by_id = {item["case_id"]: item for item in hierarchy["cases"]}
    queue_ids = [item["case_id"] for item in authoritative_queue]
    if len(queue_ids) != len(set(queue_ids)):
        raise RuntimeError("duplicate case in authoritative review queue")

    all_chunk_ids: set[str] = set()
    for review_case in authoritative_queue:
        all_chunk_ids.update(item for solution in review_case["acceptable_evidence_sets"] for item in solution)
        all_chunk_ids.update(review_case["v3"]["mapped_chunk_ids"])
        all_chunk_ids.update(item["chunk_id"] for item in review_case["selected_evidence"])

    db = SessionLocal()
    try:
        chunks, lineage = hydrate_chunks(db, all_chunk_ids)
    finally:
        db.close()

    packets = []
    for review_case in authoritative_queue:
        case = hierarchy_by_id[review_case["case_id"]]
        source_ids = source_id_map(review_case)
        by_source = {value: key for key, value in source_ids.items()}
        candidates = candidate_map(case)
        expected_solutions = [
            [snapshot(chunk_id, chunks=chunks, lineage=lineage, source_ids=source_ids, candidates=candidates) for chunk_id in solution]
            for solution in review_case["acceptable_evidence_sets"]
        ]
        expected_unique = {
            item["chunk_id"]: item for solution in expected_solutions for item in solution
        }
        actual = [
            snapshot(chunk_id, chunks=chunks, lineage=lineage, source_ids=source_ids, candidates=candidates)
            for chunk_id in review_case["v3"]["mapped_chunk_ids"]
        ]
        selected = [
            snapshot(item["chunk_id"], chunks=chunks, lineage=lineage, source_ids=source_ids, candidates=candidates)
            for item in review_case["selected_evidence"]
        ]
        actual_ids = {item["chunk_id"] for item in actual}
        selected_ids = {item["chunk_id"] for item in selected}
        required_matrix = [
            {
                "chunk_id": item["chunk_id"],
                "source_id": item["source_id"],
                "selected": item["chunk_id"] in selected_ids,
                "cited": item["chunk_id"] in actual_ids,
                "retrieval_origin": item["retrieval_origin"],
                "legal_locator": item["legal_locator"],
            }
            for item in expected_unique.values()
        ]
        metrics = case["metrics_v2"]
        reasons = list(review_case["review_reasons"])
        packet = {
            "case_id": case["case_id"],
            "category": case["category"],
            "question": case["question"],
            "answerable": case["answerable"],
            "review_reasons": reasons,
            "expected_answer_behavior": {
                "source_reference": case["source_reference"],
                "notes": case["notes"],
                "contract": "Answer only if at least one acceptable evidence set supports the exact proposition; otherwise abstain.",
                "exact_generated_answer_not_required": True,
            },
            "v2": review_case["v2"],
            "v3": review_case["v3"],
            "expected_evidence_solutions": expected_solutions,
            "actual_cited_sources": actual,
            "selected_context": selected,
            "evidence_shape": {
                "base_retrieval_count": sum(item["retrieval_origin"] == "RETRIEVAL" for item in selected),
                "hierarchy_recovered_count": sum(item["retrieval_origin"] == "HIERARCHY_CHILD" for item in selected),
                "multi_evidence": bool(metrics["is_multi_evidence"]),
                "multi_document": bool(metrics["is_multi_document"]),
                "context_token_count": case["block5"]["context_token_count"],
            },
            "required_evidence_matrix": required_matrix,
            "engineering_assessment": {
                "retrieval_expected_complete": metrics["retrieval_evidence"]["complete"],
                "context_expected_complete": metrics["context_evidence"]["complete"],
                "v3_status_valid": review_case["v3"]["answerability_validation"] == "PASS",
                "citation_structurally_valid": not review_case["v3"]["invalid_citations"],
                "expected_source_complete": review_case["v3"]["expected_source_complete"],
                "legal_correctness_not_automatically_determined": True,
            },
            "source_comparison": None,
            "qualified_answer_review": None,
            "gain_review": None,
            "multi_evidence_review": None,
            "unresolved_abstention_review": None,
            "dataset_review_candidate": None,
            "human_decision": {
                "answer_legally_supported": None,
                "actual_citation_acceptable": None,
                "expected_source_mismatch_acceptable": None,
                "qualification_acceptable": None,
                "unsupported_proposition_present": None,
                "severity": None,
                "reviewer_note": None,
                "final_decision": None,
            },
        }
        if UNEXPECTED_REASON in reasons:
            packet["source_comparison"] = structural_relationship(list(expected_unique.values()), actual)
        if QUALIFIED_REASON in reasons:
            packet["qualified_answer_review"] = {
                "direct_expected_chunks_cited": sorted(set(expected_unique) & actual_ids),
                "additional_cited_chunks": sorted(actual_ids - set(expected_unique)),
                "answer_segments": answer_segments(review_case["v3"]["public_answer_text"], by_source, set(expected_unique)),
                "review_focus": "Determine whether propositions citing only additional selected evidence are responsive supplementary measures or overbroad relative to the specific threshold in the question.",
                "rewrite_performed": False,
                "human_options": ["ACCEPT_QUALIFIED_ANSWER", "REJECT_QUALIFIED_ANSWER"],
            }
        if GAIN_REASON in reasons:
            packet["gain_review"] = {
                "v2_status": review_case["v2"]["answerability_status"],
                "v2_answer": review_case["v2"]["public_answer_text"],
                "v3_status": review_case["v3"]["answerability_status"],
                "v3_answer": review_case["v3"]["public_answer_text"],
                "v3_cited_chunk_ids": review_case["v3"]["mapped_chunk_ids"],
                "grounding_weakened": None,
            }
        if MULTI_REASON in reasons:
            packet["multi_evidence_review"] = {
                "required_piece_count": len(expected_unique),
                "required_pieces_selected": sum(item["selected"] for item in required_matrix),
                "required_pieces_cited": sum(item["cited"] for item in required_matrix),
                "required_evidence_matrix": required_matrix,
                "combined_correctly": None,
            }
        if UNRESOLVED_REASON in reasons:
            packet["unresolved_abstention_review"] = {
                "classification": "FALSE_ABSTENTION" if metrics["context_evidence"]["complete"] else "EXPECTED_EVIDENCE_NOT_IN_CONTEXT",
                "out_of_scope_for_v3_activation_fix": case["case_id"] == "v2_civil_scope",
                "future_target": "CONTEXT_SELECTION_V2" if case["case_id"] == "v2_civil_scope" else "RETRIEVAL_OR_CONTEXT_DIAGNOSIS",
            }
        packets.append(packet)

    counts = {
        "total": len(packets),
        "unexpected_source": sum(UNEXPECTED_REASON in item["review_reasons"] for item in packets),
        "qualified_answer": sum(QUALIFIED_REASON in item["review_reasons"] for item in packets),
        "v3_answerability_gain": sum(GAIN_REASON in item["review_reasons"] for item in packets),
        "multi_evidence": sum(MULTI_REASON in item["review_reasons"] for item in packets),
        "unresolved_abstention": sum(UNRESOLVED_REASON in item["review_reasons"] for item in packets),
    }
    return {
        "report_id": "legal-rag-v3-human-legal-review-gate-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "review_queue_source": str(SOURCE_REPORT.relative_to(ROOT)),
        "review_queue_source_sha256": sha256(SOURCE_REPORT),
        "no_llm_judge": True,
        "evaluation_rerun": False,
        "production_behavior_changed": False,
        "integrity": integrity,
        "queue_summary": counts,
        "queue_case_ids": queue_ids,
        "case_packets": packets,
        "decision_field_allowed_values": {
            "answer_legally_supported": ["YES", "NO", "UNCLEAR"],
            "actual_citation_acceptable": ["YES", "NO", "UNCLEAR"],
            "expected_source_mismatch_acceptable": ["YES", "NO", "N/A"],
            "qualification_acceptable": ["YES", "NO", "N/A"],
            "unsupported_proposition_present": ["YES", "NO", "UNCLEAR"],
            "severity": ["NONE", "MINOR", "MAJOR", "BLOCKER"],
            "final_decision": ["ACCEPT", "REJECT", "NEEDS_EXPERT_REVIEW"],
        },
        "activation_gate": {
            "engineering_validation": "PASS",
            "human_legal_review": "PENDING",
            "rules": [
                "No reviewed case contains a confirmed unsupported legal proposition.",
                "No unexpected-source case is judged materially misleading.",
                "Qualified-answer wording is accepted or determined non-blocking.",
                "No V3 answerability gain is a hallucinated gain.",
                "No BLOCKER decision remains unresolved.",
                "UNCLEAR decisions receive expert legal review before activation.",
            ],
            "automatic_failure_for_expected_source_mismatch": False,
            "ready_for_activation": False,
        },
        "frozen_dataset_mutation": False,
    }


def locator_text(source: dict[str, Any]) -> str:
    loc = source["legal_locator"]
    parts = []
    for label, key in (("Điều", "article"), ("Khoản", "clause"), ("Điểm", "point")):
        value = loc.get(key)
        if value and value.get("number"):
            parts.append(f"{label} {value['number']}")
    parts.append(f"tr. {source['page_start']}–{source['page_end']}")
    return ", ".join(parts)


def render_source(source: dict[str, Any], heading: str) -> list[str]:
    metadata = source["metadata_json"]
    source_label = f" / {source['source_id']}" if source["source_id"] else ""
    return [
        f"#### {heading}: `{source['chunk_id']}`{source_label}",
        "",
        f"- Document: `{source['document_id']}` — {metadata.get('document_type', '')} {metadata.get('document_number', '')}; `{source['filename']}`",
        f"- Title/authority/date: {metadata.get('title') or 'not available'}; {metadata.get('issuing_authority') or 'not available'}; {metadata.get('issued_date') or 'not available'}",
        f"- Legal unit: {locator_text(source)}; legal_unit_id `{source['legal_unit_id']}`",
        f"- Origin: `{source['retrieval_origin']}`; selected: `{source['selected']}`; retrieval rank: `{source['retrieval_final_rank']}`",
        "",
        quoted(source["content_text"]),
        "",
    ]


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Legal-RAG-V3 Human Legal Review Gate V1",
        "",
        "Status: **READY FOR HUMAN REVIEW — LEGAL DECISIONS UNFILLED**",
        "",
        "This artifact uses no LLM judge and supplies no final legal judgment. The queue is copied from the existing production-validation report; evaluation was not rerun and frozen labels were not changed.",
        "",
        "## Integrity and queue",
        "",
    ]
    for key, value in result["integrity"].items():
        lines.append(f"- {key}: `{value['actual']}` — {'MATCH' if value['match'] else 'MISMATCH'}")
    summary = result["queue_summary"]
    lines.extend([
        "",
        f"Authoritative queue: **{summary['total']} cases**; unexpected source {summary['unexpected_source']}, qualified answer {summary['qualified_answer']}, V3 gains {summary['v3_answerability_gain']}, multi-evidence {summary['multi_evidence']}, unresolved abstentions {summary['unresolved_abstention']}.",
        "",
        "## Reviewer instructions",
        "",
        "Determine whether each actual citation supports the proposition, whether expected and actual sources are legally equivalent/supplementary/conflicting, whether the answer introduces unsupported propositions, and whether qualification and multi-source synthesis are legally justified. Structural validity and expected-source matching are engineering signals only.",
        "",
    ])
    for packet in result["case_packets"]:
        lines.extend([
            f"## {packet['case_id']} — {packet['category']}",
            "",
            f"**Review reasons:** `{json.dumps(packet['review_reasons'])}`",
            "",
            f"**Question:** {packet['question']}",
            "",
            f"**Expected behavior/reference:** {' — '.join(value for value in (packet['expected_answer_behavior']['source_reference'], packet['expected_answer_behavior']['notes']) if value)}",
            "",
            "| Version | Status | Expected-source complete | Answer |",
            "|---|---|---:|---|",
            f"| V2 | `{packet['v2']['answerability_status']}` | `{packet['v2']['expected_source_complete']}` | {md(packet['v2']['public_answer_text'] or '(abstained)')} |",
            f"| V3 | `{packet['v3']['answerability_status']}` | `{packet['v3']['expected_source_complete']}` | {md(packet['v3']['public_answer_text'] or '(abstained)')} |",
            "",
            f"**Engineering assessment:** retrieval expected complete `{packet['engineering_assessment']['retrieval_expected_complete']}`; context expected complete `{packet['engineering_assessment']['context_expected_complete']}`; status valid `{packet['engineering_assessment']['v3_status_valid']}`; citation structurally valid `{packet['engineering_assessment']['citation_structurally_valid']}`. Legal correctness remains unfilled.",
            "",
            f"**Evidence shape:** base {packet['evidence_shape']['base_retrieval_count']}; hierarchy recovered {packet['evidence_shape']['hierarchy_recovered_count']}; multi-evidence `{packet['evidence_shape']['multi_evidence']}`; multi-document `{packet['evidence_shape']['multi_document']}`; context tokens {packet['evidence_shape']['context_token_count']}.",
            "",
            "### Required evidence matrix",
            "",
            "| Chunk | Source ID | Selected | Cited | Origin | Legal unit |",
            "|---|---|---:|---:|---|---|",
        ])
        for item in packet["required_evidence_matrix"]:
            loc = {"legal_locator": item["legal_locator"], "page_start": "?", "page_end": "?"}
            article = (item["legal_locator"].get("article") or {}).get("number") or "—"
            clause = (item["legal_locator"].get("clause") or {}).get("number") or "—"
            point = (item["legal_locator"].get("point") or {}).get("number") or "—"
            lines.append(f"| `{item['chunk_id']}` | `{item['source_id'] or 'not selected'}` | {item['selected']} | {item['cited']} | `{item['retrieval_origin']}` | Điều {article}, Khoản {clause}, Điểm {point} |")
        lines.extend(["", "### Expected source text", ""])
        for solution_index, solution in enumerate(packet["expected_evidence_solutions"], start=1):
            lines.append(f"**Acceptable solution {solution_index}**")
            lines.append("")
            for source in solution:
                lines.extend(render_source(source, "Expected"))
        lines.extend(["### Actual cited source text", ""])
        if packet["actual_cited_sources"]:
            for source in packet["actual_cited_sources"]:
                lines.extend(render_source(source, "Actual"))
        else:
            lines.extend(["No V3 source was cited because the model abstained.", ""])

        if packet["source_comparison"]:
            comparison = packet["source_comparison"]
            lines.extend([
                "### Unexpected-source deterministic comparison",
                "",
                f"- Document relationship: `{comparison['document_relationship']}`",
                f"- Article/clause relationship: `{comparison['article_clause_relationship']}`",
                "- Overlapping legal proposition: **PENDING HUMAN REVIEW**",
                "- Differing legal proposition: **PENDING HUMAN REVIEW**",
                "- Review label: **INSUFFICIENT FOR AUTOMATIC DETERMINATION**",
                "",
            ])
        if packet["qualified_answer_review"]:
            review = packet["qualified_answer_review"]
            lines.extend([
                "### Qualified-answer focus",
                "",
                f"- Direct expected chunks cited: `{json.dumps(review['direct_expected_chunks_cited'])}`",
                f"- Additional cited chunks: `{json.dumps(review['additional_cited_chunks'])}`",
                f"- Review focus: {review['review_focus']}",
                "- Human choice: **ACCEPT QUALIFIED ANSWER / REJECT QUALIFIED ANSWER**",
                "",
            ])
            for segment in review["answer_segments"]:
                lines.append(f"- `{segment['citation_scope']}` — {segment['text']}")
            lines.append("")
        if packet["multi_evidence_review"]:
            review = packet["multi_evidence_review"]
            lines.extend([
                "### Multi-evidence review",
                "",
                f"Required pieces: {review['required_piece_count']}; selected: {review['required_pieces_selected']}; cited: {review['required_pieces_cited']}. Whether the answer combines them correctly is **PENDING HUMAN REVIEW**.",
                "",
            ])
        if packet["unresolved_abstention_review"]:
            review = packet["unresolved_abstention_review"]
            lines.extend([
                "### Unresolved abstention",
                "",
                f"- Engineering classification: `{review['classification']}`",
                f"- Out of scope for V3 activation fix: `{review['out_of_scope_for_v3_activation_fix']}`",
                f"- Future target: `{review['future_target']}`",
                "",
            ])

        lines.extend([
            "### Selected context inventory",
            "",
            "| Source | Chunk | Origin | Rank | Legal unit | Text preview |",
            "|---|---|---|---:|---|---|",
        ])
        for source in packet["selected_context"]:
            lines.append(f"| `{source['source_id']}` | `{source['chunk_id']}` | `{source['retrieval_origin']}` | {source['retrieval_final_rank']} | {md(locator_text(source))} | {md(compact(source['content_text']))} |")
        lines.extend([
            "",
            "**Human judgment required:** answer support, citation acceptability, source mismatch, qualification, unsupported propositions, severity, and final decision. No field is pre-filled.",
            "",
            "---",
            "",
        ])
    lines.extend([
        "## Human activation gate",
        "",
    ])
    for rule in result["activation_gate"]["rules"]:
        lines.append(f"- {rule}")
    lines.extend([
        "",
        "An expected-source mismatch does not automatically fail V3. Frozen datasets and metrics remain unchanged. V3 is not ready for activation until the editable review form contains no unresolved BLOCKER and every UNCLEAR case has received expert legal review.",
        "",
        "## Existing UI inspection",
        "",
        "Open `http://localhost:5173/evaluation`, select **Evaluation V2**, and open a queued case to inspect frozen expected/measured artifacts. The existing drawer can launch a real rerun, but the current production default is V2; do not treat such a rerun as a V3 review result. Use this packet for the recorded V3 output. The chunk-detail drawer can inspect exact chunk metadata. No UI change is required.",
    ])
    return "\n".join(lines).rstrip() + "\n"


def render_form(result: dict[str, Any]) -> str:
    lines = [
        "# Legal-RAG-V3 Human Review Form V1",
        "",
        "Reviewer: ____________________", "", "Role/qualification: ____________________", "", "Date: ____________________", "",
        "Use the evidence packet in `legal_rag_v3_human_legal_review_gate_v1.md`. Do not edit frozen datasets or expected-source labels from this form.",
        "",
    ]
    for packet in result["case_packets"]:
        mismatch = "YES" if UNEXPECTED_REASON in packet["review_reasons"] else "N/A"
        qualification = "YES" if QUALIFIED_REASON in packet["review_reasons"] else "N/A"
        lines.extend([
            f"## {packet['case_id']}", "",
            f"Category: `{packet['category']}`  ",
            f"Review reasons: `{json.dumps(packet['review_reasons'])}`", "",
            "Answer legally supported?  ",
            "- [ ] YES  - [ ] NO  - [ ] UNCLEAR", "",
            "Actual citation acceptable?  ",
            "- [ ] YES  - [ ] NO  - [ ] UNCLEAR", "",
            f"Expected-source mismatch applicable: **{mismatch}**  ",
            "Expected-source mismatch acceptable?  ",
            "- [ ] YES  - [ ] NO  - [ ] N/A", "",
            f"Qualification review applicable: **{qualification}**  ",
            "Qualification acceptable?  ",
            "- [ ] YES  - [ ] NO  - [ ] N/A", "",
            "Unsupported proposition present?  ",
            "- [ ] YES  - [ ] NO  - [ ] UNCLEAR", "",
            "Severity:  ",
            "- [ ] NONE  - [ ] MINOR  - [ ] MAJOR  - [ ] BLOCKER", "",
            "Final decision:  ",
            "- [ ] ACCEPT  - [ ] REJECT  - [ ] NEEDS EXPERT REVIEW", "",
            "Reviewer note:", "", "________________________________________________________________________________", "", "________________________________________________________________________________", "",
            "Dataset review candidate (record only; do not mutate V2):  ",
            "- [ ] NO  - [ ] YES — rationale: ____________________________________________", "",
            "---", "",
        ])
    lines.extend([
        "## Gate sign-off", "",
        "Confirmed unsupported legal propositions: ____________________", "",
        "Materially misleading unexpected-source cases: ____________________", "",
        "Unresolved BLOCKER cases: ____________________", "",
        "UNCLEAR cases escalated to expert legal review: ____________________", "",
        "Activation recommendation:  ",
        "- [ ] PROCEED TO LEGAL-RAG-V3 ACTIVATION + BLOCK 6 RE-FREEZE", "- [ ] RETURN TO DESIGN", "- [ ] DATASET REVIEW REQUIRED", "",
        "Approver signature: ____________________", "",
    ])
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    result = build()
    OUTPUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(result), encoding="utf-8")
    FORM_MD.write_text(render_form(result), encoding="utf-8")
    print(json.dumps({
        "integrity": {key: value["match"] for key, value in result["integrity"].items()},
        "queue_summary": result["queue_summary"],
        "outputs": [str(path.relative_to(ROOT)) for path in (OUTPUT_MD, OUTPUT_JSON, FORM_MD)],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
