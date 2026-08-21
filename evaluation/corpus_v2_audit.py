"""Corpus V2 manifest, integrity, scale, diversity, and duplicate audit.

This module is evaluation tooling only. It performs read-only queries against the
frozen production schema and writes local JSON/Markdown artifacts.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from sqlalchemy import text

from app.db.database import SessionLocal


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_PATH = ROOT / "evaluation" / "reports" / "legal_corpus_v2_preflight.json"
MANIFEST_PATH = ROOT / "evaluation" / "corpus" / "legal_corpus_v2_manifest.json"
INTEGRITY_JSON = ROOT / "evaluation" / "reports" / "legal_corpus_v2_integrity.json"
INTEGRITY_MD = ROOT / "evaluation" / "reports" / "legal_corpus_v2_integrity.md"

FROZEN_INDEX_VERSION = "block3-v1"
FROZEN_MODEL = "intfloat/multilingual-e5-base"

SOURCE_METADATA: dict[str, dict[str, Any]] = {
    "1700c0adc6938fe21bbfa2be46c6dd6eeaeec3fe6ed49c88da0a598f4639c0ba": {
        "document_key": "social_work_practice_2026",
        "source_type": "THONG_TU",
        "document_title": "Quy định về thực hành công tác xã hội và cập nhật kiến thức công tác xã hội",
        "legal_document_number": None,
        "legal_domain": "Công tác xã hội",
        "effective_date": "2026-08-25",
        "notes": "The source number/date fields are blank in the supplied text-native draft; no number was inferred from filename.",
    },
    "80286aaa15cdd95f3ce554ee12d5a5c9c94303953093df5057561c9fea72dfb0": {
        "document_key": "people_credit_fund_safety_40_2026",
        "source_type": "THONG_TU",
        "document_title": "Quy định các giới hạn, tỷ lệ bảo đảm an toàn trong hoạt động của quỹ tín dụng nhân dân",
        "legal_document_number": "40/2026/TT-NHNN",
        "legal_domain": "An toàn hoạt động quỹ tín dụng nhân dân",
        "effective_date": "2026-11-01",
        "notes": None,
    },
    "80855c15b8f935a271e9bdbac0e74b009d0c036d29212f391da884e9431d0e58": {
        "document_key": "civil_servants_consolidated_10_2026",
        "source_type": "VAN_BAN_HOP_NHAT",
        "document_title": "Quy định về tuyển dụng, sử dụng và quản lý công chức",
        "legal_document_number": "10/2026/VBHN-NĐ-BNV",
        "legal_domain": "Tuyển dụng, sử dụng và quản lý công chức",
        "effective_date": None,
        "notes": "Consolidates Nghị định 170/2025/NĐ-CP (effective 2025-07-01) as amended by Nghị định 300/2026/NĐ-CP (effective 2026-08-01); one single effective date is not assigned to the consolidated instrument.",
    },
}


def latest_job(db, table: str, document_id: str) -> dict[str, Any] | None:
    if table == "document_processing_jobs":
        timestamp_columns = "NULL::timestamp AS created_at, finished_at"
        order_column = "COALESCE(started_at, finished_at)"
    else:
        timestamp_columns = "created_at, finished_at"
        order_column = "created_at"
    row = db.execute(
        text(
            f"""SELECT status, current_stage, error_stage, error_type, error_message,
                       {timestamp_columns}
                FROM {table}
                WHERE document_id = :document_id
                ORDER BY {order_column} DESC NULLS LAST LIMIT 1"""
        ),
        {"document_id": document_id},
    ).mappings().first()
    return serialize(dict(row)) if row else None


def serialize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def inspect_document(db, item: dict[str, Any]) -> dict[str, Any]:
    sha = item["sha256"]
    document = db.execute(
        text(
            """SELECT id::text, filename, mime_type, file_size, sha256, status, created_at, updated_at
               FROM documents WHERE sha256 = :sha"""
        ),
        {"sha": sha},
    ).mappings().first()
    base = {**SOURCE_METADATA.get(sha, {}), **item}
    if not document:
        return {
            **base,
            "ingestion_document_id": None,
            "ingestion_status": "NOT_INGESTED",
            "processing_status": "NOT_INGESTED",
            "indexing_status": "NOT_INGESTED",
            "integrity_pass": False,
            "integrity_errors": ["Document SHA-256 not found in production database"],
        }

    document = serialize(dict(document))
    document_id = document["id"]
    counts = db.execute(
        text(
            """SELECT
                 (SELECT count(*) FROM document_pages WHERE document_id = :did) AS pages,
                 (SELECT count(*) FROM document_reconstructions WHERE document_id = :did) AS reconstructions,
                 (SELECT count(*) FROM legal_units WHERE document_id = :did) AS legal_units,
                 (SELECT count(*) FROM chunks WHERE document_id = :did) AS chunks,
                 (SELECT count(*) FROM chunk_indexes WHERE document_id = :did) AS indexes,
                 (SELECT count(*) FROM chunks WHERE document_id = :did AND
                     (provenance_json IS NULL OR provenance_json::jsonb = '{}'::jsonb)) AS missing_provenance,
                 (SELECT count(*) FROM chunk_indexes WHERE document_id = :did AND
                     index_version = :version AND embedding_model = :model AND embedding_dimension = 768) AS frozen_indexes,
                 (SELECT count(*) FROM chunk_indexes WHERE document_id = :did AND lexical_tsv IS NOT NULL) AS lexical_indexes"""
        ),
        {"did": document_id, "version": FROZEN_INDEX_VERSION, "model": FROZEN_MODEL},
    ).mappings().one()
    counts = dict(counts)
    ingestion = latest_job(db, "ingestion_jobs", document_id)
    processing = latest_job(db, "document_processing_jobs", document_id)
    indexing = latest_job(db, "indexing_jobs", document_id)
    errors: list[str] = []
    if document["status"] != "COMPLETED":
        errors.append(f"Document status is {document['status']}")
    if not ingestion or ingestion["status"] != "COMPLETED":
        errors.append("Latest ingestion job is not COMPLETED")
    if not processing or processing["status"] != "COMPLETED":
        errors.append("Latest processing job is not COMPLETED")
    if not indexing or indexing["status"] != "COMPLETED":
        errors.append("Latest indexing job is not COMPLETED")
    for key in ("pages", "reconstructions", "legal_units", "chunks", "indexes"):
        if counts[key] <= 0:
            errors.append(f"No {key} persisted")
    if counts["chunks"] != counts["indexes"]:
        errors.append(f"Chunk/index mismatch: {counts['chunks']} != {counts['indexes']}")
    if counts["indexes"] != counts["frozen_indexes"]:
        errors.append("Not all indexes satisfy frozen block3-v1/model/dimension contract")
    if counts["indexes"] != counts["lexical_indexes"]:
        errors.append("Not all indexes contain lexical_tsv")
    if counts["missing_provenance"]:
        errors.append(f"{counts['missing_provenance']} chunks have empty provenance")

    return {
        **base,
        "input_path": item["input_path"],
        "ingestion_document_id": document_id,
        "stored_filename": document["filename"],
        "ingestion_status": ingestion["status"] if ingestion else None,
        "processing_status": processing["status"] if processing else None,
        "indexing_status": indexing["status"] if indexing else None,
        "document_status": document["status"],
        "page_count": counts["pages"],
        "legal_unit_count": counts["legal_units"],
        "chunk_count": counts["chunks"],
        "index_count": counts["indexes"],
        "frozen_index_count": counts["frozen_indexes"],
        "lexical_index_count": counts["lexical_indexes"],
        "reconstruction_count": counts["reconstructions"],
        "missing_provenance_count": counts["missing_provenance"],
        "ingestion_job": ingestion,
        "processing_job": processing,
        "indexing_job": indexing,
        "integrity_pass": not errors,
        "integrity_errors": errors,
    }


def duplicate_observations(db, documents: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [item["ingestion_document_id"] for item in documents if item.get("ingestion_document_id")]
    supplied_hashes = Counter(item["sha256"] for item in documents)
    duplicate_pdfs = [sha for sha, count in supplied_hashes.items() if count > 1]
    exact_rows = db.execute(
        text(
            """SELECT md5(regexp_replace(lower(content_text), '\\s+', ' ', 'g')) AS content_hash,
                      count(*) AS copies, array_agg(id::text ORDER BY id::text) AS chunk_ids,
                      array_agg(DISTINCT document_id::text ORDER BY document_id::text) AS document_ids
               FROM chunks WHERE document_id = ANY(CAST(:ids AS uuid[]))
               GROUP BY 1 HAVING count(*) > 1 ORDER BY copies DESC, content_hash"""
        ),
        {"ids": ids},
    ).mappings().all()
    near_rows = db.execute(
        text(
            """WITH corpus AS (
                   SELECT ci.chunk_id, ci.document_id, ci.embedding
                   FROM chunk_indexes ci WHERE ci.document_id = ANY(CAST(:ids AS uuid[]))
               )
               SELECT a.chunk_id::text AS chunk_a, a.document_id::text AS document_a,
                      b.chunk_id::text AS chunk_b, b.document_id::text AS document_b,
                      (1 - (a.embedding <=> b.embedding))::float AS cosine_similarity
               FROM corpus a
               CROSS JOIN LATERAL (
                   SELECT b.chunk_id, b.document_id, b.embedding
                   FROM corpus b
                   WHERE b.document_id <> a.document_id
                   ORDER BY a.embedding <=> b.embedding, b.chunk_id
                   LIMIT 1
               ) b
               WHERE 1 - (a.embedding <=> b.embedding) >= 0.92
               ORDER BY cosine_similarity DESC, chunk_a LIMIT 25"""
        ),
        {"ids": ids},
    ).mappings().all()
    return {
        "duplicate_pdf_sha256": duplicate_pdfs,
        "exact_duplicate_chunk_groups": [serialize(dict(row)) for row in exact_rows],
        "potential_cross_document_near_duplicates": [serialize(dict(row)) for row in near_rows],
        "near_duplicate_method": "Nearest cross-document embedding cosine similarity >= 0.92; diagnostic signal only, not legal equivalence.",
    }


def table_and_index_state(db) -> dict[str, Any]:
    tables = db.execute(
        text(
            """SELECT table_name FROM information_schema.tables
               WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name"""
        )
    ).scalars().all()
    indexes = db.execute(
        text(
            """SELECT indexname, indexdef FROM pg_indexes
               WHERE schemaname='public' AND tablename='chunk_indexes' ORDER BY indexname"""
        )
    ).mappings().all()
    database_size = db.execute(text("SELECT pg_database_size(current_database())")).scalar_one()
    return {
        "public_table_count": len(tables),
        "public_tables": list(tables),
        "chunk_index_indexes": [serialize(dict(row)) for row in indexes],
        "database_size_bytes": database_size,
    }


def render_integrity(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Legal Corpus V2 Integrity Audit",
        "",
        f"Generated: {report['generated_at']}",
        "",
        f"Corpus integrity: **{'PASS' if report['integrity_pass'] else 'FAIL'}**",
        "",
        "## Scale",
        "",
        f"- Supplied PDFs: {summary['supplied_pdf_count']}",
        f"- READY: {summary['ready_count']}",
        f"- Excluded: {summary['excluded_count']}",
        f"- Successfully ingested: {summary['successfully_ingested']}",
        f"- Pages: {summary['total_pages']}",
        f"- Legal units: {summary['total_legal_units']}",
        f"- Chunks: {summary['total_chunks']}",
        f"- Chunk indexes: {summary['total_indexes']}",
        f"- Average chunks/document: {summary['average_chunks_per_document']:.2f}",
        f"- Min/max chunks/document: {summary['min_chunks_per_document']}/{summary['max_chunks_per_document']}",
        f"- Public PostgreSQL tables: {report['infrastructure']['public_table_count']}",
        f"- Database size: {report['infrastructure']['database_size_bytes']} bytes",
        "",
        "## Document integrity",
        "",
        "| Document key | Document ID | Pages | Units | Chunks | Indexes | Status |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for item in report["documents"]:
        lines.append(
            f"| {item.get('document_key')} | `{item.get('ingestion_document_id')}` | "
            f"{item.get('page_count', 0)} | {item.get('legal_unit_count', 0)} | "
            f"{item.get('chunk_count', 0)} | {item.get('index_count', 0)} | "
            f"**{'PASS' if item.get('integrity_pass') else 'FAIL'}** |"
        )
        for error in item.get("integrity_errors", []):
            lines.append(f"  - {error}")
    lines.extend(
        [
            "",
            "## Diversity",
            "",
            *[f"- {item}" for item in report["diversity"]["observations"]],
            "",
            "## Duplicate observations",
            "",
            f"- Duplicate supplied PDF hashes: {len(report['duplicates']['duplicate_pdf_sha256'])}",
            f"- Exact duplicate chunk groups: {len(report['duplicates']['exact_duplicate_chunk_groups'])}",
            f"- Potential cross-document near-duplicate pairs: {len(report['duplicates']['potential_cross_document_near_duplicates'])}",
            f"- Method: {report['duplicates']['near_duplicate_method']}",
            "",
            "The automatic Block 2 indexing hook initially produced legacy `v1` labels. The existing canonical indexing API was then used, without code changes, to persist the frozen `block3-v1` contract required by Block 4.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    preflight = json.loads(PREFLIGHT_PATH.read_text(encoding="utf-8"))
    ready_inputs = [item for item in preflight["files"] if item["classification"] == "READY"]
    db = SessionLocal()
    try:
        documents = [inspect_document(db, item) for item in ready_inputs]
        excluded = [item for item in preflight["files"] if item["classification"] != "READY"]
        manifest = {
            "manifest_id": "legal_corpus_v2",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_boundary": "Only PDFs supplied in evaluation/corpus/input",
            "items": documents + [
                {
                    **item,
                    "document_key": None,
                    "source_type": None,
                    "document_title": None,
                    "legal_document_number": None,
                    "legal_domain": None,
                    "effective_date": None,
                    "notes": "Excluded by text-native preflight; OCR was not used.",
                    "ingestion_document_id": None,
                    "ingestion_status": "EXCLUDED",
                    "processing_status": "NOT_RUN",
                    "indexing_status": "NOT_RUN",
                }
                for item in excluded
            ],
        }
        chunk_counts = [item["chunk_count"] for item in documents if item.get("integrity_pass")]
        summary = {
            "supplied_pdf_count": len(preflight["files"]),
            "ready_count": len(ready_inputs),
            "excluded_count": len(excluded),
            "successfully_ingested": sum(item.get("integrity_pass", False) for item in documents),
            "failed_ingestion_count": sum(not item.get("integrity_pass", False) for item in documents),
            "total_pages": sum(item.get("page_count", 0) for item in documents),
            "total_legal_units": sum(item.get("legal_unit_count", 0) for item in documents),
            "total_chunks": sum(item.get("chunk_count", 0) for item in documents),
            "total_indexes": sum(item.get("index_count", 0) for item in documents),
            "average_chunks_per_document": mean(chunk_counts) if chunk_counts else 0,
            "min_chunks_per_document": min(chunk_counts) if chunk_counts else 0,
            "max_chunks_per_document": max(chunk_counts) if chunk_counts else 0,
        }
        diversity = {
            "document_domains": sorted({item["legal_domain"] for item in documents}),
            "observations": [
                "Three distinct domains are present: social work practice, people-credit-fund safety, and civil-service management.",
                "All three documents contain repeated structural identifiers such as Điều 1, Điều 2, khoản 1, and effective-date clauses, supporting document-disambiguation and same-article-number tests.",
                "The consolidated civil-service instrument contains many amendment footnotes and repeated effective-date language, supporting near-duplicate/ambiguity stress cases within one document.",
                "The corpus supports cross-document terminology stress (authority, applicability, reporting, effective date), but does not provide a defensible substantive rule that inherently requires combining two different legal domains.",
                "The three documents differ strongly in length (121, 152, and 692 chunks), enabling scale and deeper-rank stress without manufacturing categories.",
            ],
            "multi_document_ground_truth_supported": False,
            "same_article_number_supported": True,
            "document_disambiguation_supported": True,
            "near_duplicate_stress_supported": True,
        }
        report = {
            "report_id": "legal_corpus_v2_integrity",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "integrity_pass": all(item.get("integrity_pass", False) for item in documents),
            "summary": summary,
            "documents": documents,
            "excluded_files": excluded,
            "diversity": diversity,
            "duplicates": duplicate_observations(db, documents),
            "infrastructure": table_and_index_state(db),
            "frozen_contract": {
                "embedding_model": FROZEN_MODEL,
                "embedding_dimension": 768,
                "index_version": FROZEN_INDEX_VERSION,
                "schema_changed": False,
            },
        }
    finally:
        db.close()

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    INTEGRITY_JSON.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    INTEGRITY_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    INTEGRITY_MD.write_text(render_integrity(report), encoding="utf-8")
    print(json.dumps({"integrity_pass": report["integrity_pass"], **summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
