"""Seed the independent benchmark state from the committed real-data fixture."""

from __future__ import annotations

import json
import hashlib
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, text

from app.db.database import SessionLocal
from app.models.chunk import Chunk
from app.models.chunk_index import ChunkIndex
from app.models.document import Document, DocumentStatus
from app.models.document_page import DocumentPage
from app.models.legal_unit import LegalUnit
from app.storage.minio_client import minio_client
from evaluation.benchmark.fixture import fixture_sha256, load_fixture
from evaluation.benchmark.runtime import assert_benchmark_runtime
from evaluation.benchmark.snapshot import snapshot


def _uuid(value):
    return UUID(value) if value else None


def _datetime(value):
    return datetime.fromisoformat(value) if value else None


def _digest(items) -> str:
    return hashlib.sha256("\n".join(sorted(str(item) for item in items)).encode("utf-8")).hexdigest()


def _expected_snapshot(fixture: dict) -> dict:
    document_id = fixture["document"]["id"]
    return {
        "documents": 1, "chunks": len(fixture["chunks"]), "chunk_indexes": len(fixture["chunk_indexes"]), "objects": 1,
        "document_ids_sha256": _digest([document_id]),
        "chunk_ids_sha256": _digest(row["id"] for row in fixture["chunks"]),
        "chunk_index_ids_sha256": _digest(row["id"] for row in fixture["chunk_indexes"]),
        "object_names_sha256": _digest([f"{document_id}/original.pdf"]),
    }


def _assert_empty_or_seeded(db, fixture: dict) -> bool:
    populated = [
        name for name, model in (("documents", Document), ("chunks", Chunk), ("chunk_indexes", ChunkIndex))
        if db.scalar(select(model.id).limit(1)) is not None
    ]
    if populated:
        if snapshot() == _expected_snapshot(fixture):
            return True
        raise RuntimeError(f"BENCHMARK_FIXTURE_TARGET_NOT_EMPTY:{','.join(populated)}")
    return False


def seed() -> dict:
    assert_benchmark_runtime()
    fixture = load_fixture()
    document_row = fixture["document"]
    source_pdf = Path(fixture["source_pdf_path"])
    if not source_pdf.is_file():
        raise RuntimeError("BENCHMARK_FIXTURE_SOURCE_PDF_MISSING")
    if fixture["fixture_version"] != "legal-retrieval-v1":
        raise RuntimeError("BENCHMARK_FIXTURE_VERSION_UNSUPPORTED")

    db = SessionLocal()
    try:
        already_seeded = _assert_empty_or_seeded(db, fixture)
        if already_seeded:
            return {"already_seeded": True, "fixture_sha256": fixture_sha256(), **snapshot()}
        document = Document(
            id=_uuid(document_row["id"]), user_id=document_row["user_id"], filename=document_row["filename"],
            mime_type=document_row["mime_type"], file_size=document_row["file_size"], sha256=document_row["sha256"],
            storage_uri=f"minio://{minio_client.bucket}/{document_row['id']}/original.pdf", page_count=document_row["page_count"],
            status=DocumentStatus(document_row["status"]), created_at=_datetime(document_row["created_at"]), updated_at=_datetime(document_row["updated_at"]),
        )
        db.add(document)
        db.flush()
        db.add_all(
            DocumentPage(
                id=_uuid(row["id"]), document_id=_uuid(row["document_id"]), page_number=row["page_number"],
                raw_text=row["raw_text"], char_count=row["char_count"], created_at=_datetime(row["created_at"]),
            ) for row in fixture["pages"]
        )
        db.add_all(
            LegalUnit(
                id=_uuid(row["id"]), document_id=_uuid(row["document_id"]), parent_unit_id=_uuid(row["parent_unit_id"]),
                unit_type=row["unit_type"], unit_number=row["unit_number"], unit_title=row["unit_title"], content_text=row["content_text"],
                page_start=row["page_start"], page_end=row["page_end"], char_start=row["char_start"], char_end=row["char_end"],
                level=row["level"], created_at=_datetime(row["created_at"]),
            ) for row in fixture["legal_units"]
        )
        db.flush()
        db.add_all(
            Chunk(
                id=_uuid(row["id"]), document_id=_uuid(row["document_id"]), legal_unit_id=_uuid(row["legal_unit_id"]),
                chunk_index=row["chunk_index"], content_text=row["content_text"], embedding_text=row["embedding_text"],
                page_start=row["page_start"], page_end=row["page_end"], metadata_json=row["metadata_json"],
                provenance_json=row["provenance_json"], created_at=_datetime(row["created_at"]),
            ) for row in fixture["chunks"]
        )
        db.flush()
        db.add_all(
            ChunkIndex(
                id=_uuid(row["id"]), chunk_id=_uuid(row["chunk_id"]), document_id=_uuid(row["document_id"]),
                embedding=row["embedding"], embedding_model=row["embedding_model"], embedding_dimension=row["embedding_dimension"],
                index_version=row["index_version"], created_at=_datetime(row["created_at"]), updated_at=_datetime(row["updated_at"]),
            ) for row in fixture["chunk_indexes"]
        )
        db.flush()
        db.execute(text("UPDATE chunk_indexes ci SET lexical_tsv = to_tsvector('simple', c.content_text) FROM chunks c WHERE ci.chunk_id = c.id"))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    pdf_bytes = source_pdf.read_bytes()
    if __import__("hashlib").sha256(pdf_bytes).hexdigest() != document_row["sha256"]:
        raise RuntimeError("BENCHMARK_FIXTURE_SOURCE_PDF_HASH_MISMATCH")
    minio_client.upload_pdf(document_row["id"], pdf_bytes)
    return {"fixture_sha256": fixture_sha256(), **snapshot()}


def main() -> None:
    print(json.dumps(seed(), sort_keys=True))


if __name__ == "__main__":
    main()
