"""Delete API lifecycle coverage for failed and physically orphaned documents."""
from __future__ import annotations

import hashlib
import uuid
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from minio.error import S3Error
from sqlalchemy import delete, text

from app.auth.access import DocumentAccessService
from app.auth.service import AuthService
from app.auth.worker import process_document_gc
from app.db.database import SessionLocal
from app.main import app
from app.models.auth import AuthSession, DocumentAccessGrant, GlobalDocumentAccess, User, UserRole
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus
from app.models.document_page import DocumentPage
from app.models.indexing_job import IndexingJob
from app.storage.minio_client import MinioClient


pytestmark = [pytest.mark.real_auth, pytest.mark.isolated_document_corpus]
PASSWORD = "correct horse battery staple"
ORIGIN = {"Origin": "http://localhost:5173"}


@pytest.fixture
def delete_fixture():
    db = SessionLocal()
    users: list[uuid.UUID] = []
    documents: list[uuid.UUID] = []
    try:
        yield db, users, documents
    finally:
        db.rollback()
        if documents:
            ids = [str(value) for value in documents]
            db.execute(delete(DocumentAccessGrant).where(DocumentAccessGrant.document_id.in_(documents)))
            db.execute(delete(GlobalDocumentAccess).where(GlobalDocumentAccess.document_id.in_(documents)))
            db.execute(text("DELETE FROM indexing_jobs WHERE document_id = ANY(CAST(:ids AS uuid[]))"), {"ids": ids})
            db.execute(text("DELETE FROM ingestion_jobs WHERE document_id = ANY(CAST(:ids AS uuid[]))"), {"ids": ids})
            db.execute(text("DELETE FROM document_pages WHERE document_id = ANY(CAST(:ids AS uuid[]))"), {"ids": ids})
            db.execute(delete(Document).where(Document.id.in_(documents)))
        if users:
            db.execute(delete(AuthSession).where(AuthSession.user_id.in_(users)))
            db.execute(delete(User).where(User.id.in_(users)))
        db.commit(); db.close()


def _user(db, users, role=UserRole.USER):
    user = AuthService(db).provision_user(
        f"delete-{uuid.uuid4()}@example.invalid", PASSWORD, role, must_change_password=False,
    )
    users.append(user.id)
    client = TestClient(app)
    assert client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}).status_code == 200
    return user, client


def _document(db, documents, *, state=DocumentStatus.FAILED, filename="orphan.pdf"):
    document = Document(filename=filename, mime_type="application/pdf", file_size=123, sha256=hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest(), status=state)
    db.add(document); db.commit(); documents.append(document.id)
    return document


def _run_gc_immediately(monkeypatch, deleted_objects):
    monkeypatch.setattr("app.auth.worker.minio_client.delete", lambda document_id: deleted_objects.append(document_id))
    monkeypatch.setattr("app.api.routes.documents.rq_client.enqueue_document_gc", lambda document_id, request_id: process_document_gc(document_id, request_id))


@pytest.mark.parametrize("failure_kind", ["PROCESSING", "INDEXING", "ZERO_DERIVED"])
def test_owned_failed_orphan_is_removed_from_list_and_database(delete_fixture, monkeypatch, failure_kind):
    db, users, documents = delete_fixture; owner, client = _user(db, users)
    document = _document(db, documents, filename=f"{failure_kind.lower()}-orphan.pdf")
    document_id = document.id
    DocumentAccessService(db).grant_private(owner.id, document.id)
    if failure_kind == "INDEXING":
        db.add(IndexingJob(document_id=document.id, status="FAILED", current_stage="EMBEDDING", error_stage="EMBEDDING"))
    elif failure_kind == "PROCESSING":
        db.add(DocumentPage(document_id=document.id, page_number=1, raw_text="partial", char_count=7))
        db.add(Chunk(
            document_id=document.id, legal_unit_id=None, chunk_index=0,
            content_text="partially materialized", embedding_text="partially materialized",
            page_start=1, page_end=1, metadata_json={}, provenance_json={},
        ))
    db.commit()
    deleted_objects: list[str] = []; _run_gc_immediately(monkeypatch, deleted_objects)

    response = client.delete(f"/documents/{document_id}", headers=ORIGIN)
    assert response.status_code == 202, response.text
    assert response.json() == {"access_removed": "PRIVATE", "gc_candidate": True}
    assert str(document_id) not in client.get("/documents").text
    db.expire_all()
    assert db.get(Document, document_id) is None
    assert db.execute(text("SELECT count(*) FROM indexing_jobs WHERE document_id=:id"), {"id": document_id}).scalar_one() == 0
    assert db.execute(text("SELECT count(*) FROM document_pages WHERE document_id=:id"), {"id": document_id}).scalar_one() == 0
    assert db.execute(text("SELECT count(*) FROM chunks WHERE document_id=:id"), {"id": document_id}).scalar_one() == 0
    assert str(document_id) in deleted_objects
    assert process_document_gc(str(document_id), "second-cleanup") is True


def test_admin_removes_global_orphan_without_resource_not_found(delete_fixture, monkeypatch):
    db, users, documents = delete_fixture; admin, client = _user(db, users, UserRole.ADMIN)
    document = _document(db, documents, filename="fake.pdf")
    document_id = document.id
    DocumentAccessService(db).grant_global(admin.id, document.id)
    db.add(IndexingJob(document_id=document.id, status="FAILED", current_stage="EMBEDDING", error_stage="EMBEDDING")); db.commit()
    deleted_objects: list[str] = []; _run_gc_immediately(monkeypatch, deleted_objects)

    response = client.delete(f"/documents/{document_id}", headers=ORIGIN)
    assert response.status_code == 202, response.text
    assert response.json() == {"access_removed": "GLOBAL", "gc_candidate": True}
    db.expire_all()
    assert db.get(Document, document_id) is None
    assert str(document_id) in deleted_objects


def test_global_removal_preserves_shared_document_with_remaining_private_access(delete_fixture, monkeypatch):
    db, users, documents = delete_fixture; admin, admin_client = _user(db, users, UserRole.ADMIN); other, _ = _user(db, users)
    document = _document(db, documents, filename="shared.pdf")
    DocumentAccessService(db).grant_global(admin.id, document.id); DocumentAccessService(db).grant_private(other.id, document.id)
    deleted_objects: list[str] = []; _run_gc_immediately(monkeypatch, deleted_objects)
    response = admin_client.delete(f"/documents/{document.id}", headers=ORIGIN)
    assert response.status_code == 202 and response.json()["gc_candidate"] is False
    assert db.get(Document, document.id) is not None
    assert not deleted_objects


def test_nonexistent_and_unauthorized_documents_remain_404(delete_fixture):
    db, users, documents = delete_fixture; owner, _ = _user(db, users); other, other_client = _user(db, users)
    document = _document(db, documents); DocumentAccessService(db).grant_private(owner.id, document.id)
    assert other_client.delete(f"/documents/{document.id}", headers=ORIGIN).status_code == 404
    assert other_client.delete(f"/documents/{uuid.uuid4()}", headers=ORIGIN).status_code == 404


def test_missing_owned_object_is_idempotent_but_unexpected_storage_errors_are_not_hidden():
    client = MinioClient.__new__(MinioClient)
    client.bucket = "documents"
    client.client = Mock()
    client.client.remove_object.side_effect = S3Error(
        None, "NoSuchKey", "already absent", "resource", "request", "host",
    )
    client.delete(str(uuid.uuid4()))
    client.client.remove_object.assert_called_once()
