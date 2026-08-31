"""Seed the independent benchmark state from the committed real-data fixture."""

from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, text

from app.db.database import SessionLocal
from app.models.chunk import Chunk
from app.models.chunk_index import ChunkIndex
from app.models.document import Document, DocumentStatus
from app.models.document_page import DocumentPage
from app.models.legal_unit import LegalUnit
from app.storage.minio_client import minio_client
from evaluation.benchmark.fixture import fixture_object_root, fixture_sha256, load_fixture
from evaluation.benchmark.runtime import assert_benchmark_runtime
from evaluation.benchmark.snapshot import snapshot


def _uuid(value):
    return UUID(value) if value else None


def _datetime(value):
    return datetime.fromisoformat(value) if value else None


def _digest(items) -> str:
    return hashlib.sha256("\n".join(sorted(str(item) for item in items)).encode("utf-8")).hexdigest()


def _expected_snapshot(fixture: dict) -> dict:
    return {
        "documents": len(fixture["documents"]), "chunks": len(fixture["chunks"]),
        "chunk_indexes": len(fixture["chunk_indexes"]), "objects": len(fixture["objects"]),
        "document_ids_sha256": _digest(row["id"] for row in fixture["documents"]),
        "chunk_ids_sha256": _digest(row["id"] for row in fixture["chunks"]),
        "chunk_index_ids_sha256": _digest(row["id"] for row in fixture["chunk_indexes"]),
        "object_names_sha256": _digest(row["key"] for row in fixture["objects"]),
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
    if fixture["fixture_version"] != "legal-retrieval-v2":
        raise RuntimeError("BENCHMARK_FIXTURE_VERSION_UNSUPPORTED")

    db = SessionLocal()
    try:
        already_seeded = _assert_empty_or_seeded(db, fixture)
        if already_seeded:
            return {"already_seeded": True, "fixture_sha256": fixture_sha256(), **snapshot()}
        db.add_all(
            Document(
                id=_uuid(row["id"]), user_id=row["user_id"], filename=row["filename"], mime_type=row["mime_type"],
                file_size=row["file_size"], sha256=row["sha256"], storage_uri=f"minio://{minio_client.bucket}/{row['id']}/original.pdf",
                page_count=row["page_count"], status=DocumentStatus(row["status"]), created_at=_datetime(row["created_at"]),
                updated_at=_datetime(row["updated_at"]),
            ) for row in fixture["documents"]
        )
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

    object_root = fixture_object_root()
    for object_row in fixture["objects"]:
        source_object = object_root / object_row["key"]
        if not source_object.is_file():
            raise RuntimeError("BENCHMARK_FIXTURE_SOURCE_OBJECT_MISSING")
        object_bytes = source_object.read_bytes()
        if hashlib.sha256(object_bytes).hexdigest() != object_row["sha256"]:
            raise RuntimeError("BENCHMARK_FIXTURE_SOURCE_OBJECT_HASH_MISMATCH")
        minio_client.client.put_object(
            minio_client.bucket, object_row["key"], io.BytesIO(object_bytes), len(object_bytes), content_type="application/pdf"
        )
    return {"fixture_sha256": fixture_sha256(), **snapshot()}


def main() -> None:
    print(json.dumps(seed(), sort_keys=True))


if __name__ == "__main__":
    main()
