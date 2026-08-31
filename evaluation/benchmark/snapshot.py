"""Read-only deterministic integrity snapshots for benchmark state."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import select

from app.db.database import SessionLocal
from app.models.chunk import Chunk
from app.models.chunk_index import ChunkIndex
from app.models.document import Document
from app.storage.minio_client import minio_client
from evaluation.benchmark.runtime import assert_benchmark_runtime


def _digest(items) -> str:
    material = "\n".join(sorted(str(item) for item in items)).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def snapshot() -> dict:
    """Return only deterministic read-only facts about the active benchmark target."""
    assert_benchmark_runtime()
    db = SessionLocal()
    try:
        document_ids = list(db.scalars(select(Document.id)))
        chunk_ids = list(db.scalars(select(Chunk.id)))
        index_ids = list(db.scalars(select(ChunkIndex.id)))
    finally:
        db.close()
    object_names = [item.object_name for item in minio_client.client.list_objects(minio_client.bucket, recursive=True)]
    return {
        "documents": len(document_ids),
        "chunks": len(chunk_ids),
        "chunk_indexes": len(index_ids),
        "objects": len(object_names),
        "document_ids_sha256": _digest(document_ids),
        "chunk_ids_sha256": _digest(chunk_ids),
        "chunk_index_ids_sha256": _digest(index_ids),
        "object_names_sha256": _digest(object_names),
    }


def main() -> None:
    print(json.dumps(snapshot(), sort_keys=True))


if __name__ == "__main__":
    main()
