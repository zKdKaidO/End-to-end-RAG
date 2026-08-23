import hashlib
import threading
import time
import uuid
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text

from app.api.routes import auth as auth_routes
from app.api.routes.answer import get_answer_service
from app.auth.access import DocumentAccessService
from app.auth.passwords import hash_password
from app.auth.scope import UserRetrievalScope
from app.auth.service import AuthService, token_hash
from app.auth.worker import collect_canonical_document, process_account_deletion
from app.chat.service import ChatHistoryService
from app.context.service import ContextBuilderService
from app.db.database import SessionLocal
from app.main import app
from app.models.auth import (
    AccountDeletionJob, AuthSession, DocumentAccessGrant, GlobalDocumentAccess,
    User, UserRole, UserStatus, utcnow,
)
from app.models.chat import (
    ChatMessage, ChatSession, ChatTurn, DeliveryState, MessageCitationSnapshot,
    MessageRole, TurnState,
)
from app.models.chunk import Chunk
from app.models.chunk_index import ChunkIndex
from app.models.document import Document, DocumentStatus
from app.repositories.document_repo import DocumentRepository
from app.repositories.job_repo import JobRepository
from app.retrieval.repository import RetrievalRepository
from app.retrieval.schemas import RetrievalRequest
from app.retrieval.service import RetrievalService, validate_request
from app.services.upload_service import UploadService


pytestmark = pytest.mark.real_auth
ORIGIN = {"Origin": "http://localhost:5173"}
PASSWORD = "correct horse battery staple"


@pytest.fixture
def db():
    session = SessionLocal()
    created_users: list[uuid.UUID] = []
    created_documents: list[uuid.UUID] = []
    yield session, created_users, created_documents
    session.rollback()
    if created_users:
        session.execute(delete(ChatSession).where(ChatSession.user_id.in_(created_users)))
        session.execute(delete(AuthSession).where(AuthSession.user_id.in_(created_users)))
        session.execute(delete(DocumentAccessGrant).where(DocumentAccessGrant.user_id.in_(created_users)))
        session.execute(delete(User).where(User.id.in_(created_users)))
        session.execute(delete(AccountDeletionJob).where(AccountDeletionJob.subject_user_id.in_(created_users)))
    if created_documents:
        session.execute(text("DELETE FROM indexing_jobs WHERE document_id = ANY(CAST(:ids AS uuid[]))"), {"ids": [str(value) for value in created_documents]})
        session.execute(text("DELETE FROM ingestion_jobs WHERE document_id = ANY(CAST(:ids AS uuid[]))"), {"ids": [str(value) for value in created_documents]})
        session.execute(text("DELETE FROM document_pages WHERE document_id = ANY(CAST(:ids AS uuid[]))"), {"ids": [str(value) for value in created_documents]})
        session.execute(delete(Document).where(Document.id.in_(created_documents)))
    session.commit()
    session.close()


def user(db, created, prefix: str, role=UserRole.USER):
    item = AuthService(db).provision_user(
        f"{prefix}-{uuid.uuid4()}@example.invalid", PASSWORD, role, must_change_password=False,
    )
    created.append(item.id)
    return item


def login(item: User) -> TestClient:
    client = TestClient(app)
    response = client.post("/api/v1/auth/login", json={"email": item.email, "password": PASSWORD})
    assert response.status_code == 200
    return client


def document(db, created_documents, text_value="fixture") -> Document:
    item = Document(
        filename=f"{text_value}.pdf", mime_type="application/pdf", file_size=10,
        sha256=hashlib.sha256(f"{text_value}-{uuid.uuid4()}".encode()).hexdigest(),
        status=DocumentStatus.COMPLETED, created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(item); db.commit(); created_documents.append(item.id)
    return item


def test_opaque_session_login_logout_password_change_and_no_enumeration(db):
    session, users, _documents = db
    alice = user(session, users, "alice")
    client = login(alice)
    assert alice.password_hash.startswith("$argon2id$")
    raw = client.cookies.get("legal_rag_session")
    assert raw and len(raw) >= 40
    stored = session.scalar(select(AuthSession).where(AuthSession.user_id == alice.id))
    assert stored.token_hash == token_hash(raw) and stored.token_hash != raw
    cookie_probe = TestClient(app).post(
        "/api/v1/auth/login", json={"email": alice.email, "password": PASSWORD}
    )
    cookie_contract = cookie_probe.headers["set-cookie"].lower()
    assert "httponly" in cookie_contract and "samesite=lax" in cookie_contract and "path=/" in cookie_contract
    frontend_source = "\n".join(
        path.read_text(encoding="utf-8") for path in Path("frontend/src").rglob("*.ts*")
    )
    assert "legal_rag_session" not in frontend_source and "sessionStorage" not in frontend_source
    assert client.get("/api/v1/auth/me").json()["email"] == alice.email

    unknown = TestClient(app).post("/api/v1/auth/login", json={"email": "missing@example.invalid", "password": "wrong password value"})
    wrong = TestClient(app).post("/api/v1/auth/login", json={"email": alice.email, "password": "wrong password value"})
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()

    changed = client.post(
        "/api/v1/auth/change-password", headers=ORIGIN,
        json={"current_password": PASSWORD, "new_password": "a newly selected long passphrase"},
    )
    assert changed.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    assert session.scalar(select(func.count(AuthSession.id)).where(AuthSession.user_id == alice.id, AuthSession.revoked_at.is_(None))) == 0


def test_expired_revoked_disabled_deleting_forged_and_missing_sessions_are_rejected(db):
    session, users, _documents = db
    alice = user(session, users, "negative")
    client = login(alice)
    auth_session = session.scalar(select(AuthSession).where(AuthSession.user_id == alice.id))
    auth_session.expires_at = utcnow() - timedelta(seconds=1); session.commit()
    assert client.get("/api/v1/auth/me").status_code == 401

    alice.status = UserStatus.ACTIVE.value
    auth_session.expires_at = utcnow() + timedelta(hours=1)
    auth_session.revoked_at = utcnow()
    session.commit()
    assert client.get("/api/v1/auth/me").status_code == 401

    for state in (UserStatus.DISABLED.value, UserStatus.DELETING.value):
        alice.status = state; session.commit()
        response = TestClient(app).post("/api/v1/auth/login", json={"email": alice.email, "password": PASSWORD})
        assert response.status_code == 401
    assert TestClient(app).get("/api/v1/auth/me").status_code == 401
    forged = TestClient(app); forged.cookies.set("legal_rag_session", "forged-token")
    assert forged.get("/api/v1/auth/me").status_code == 401


def test_history_idor_returns_uniform_404(db):
    session, users, _documents = db
    alice, bob = user(session, users, "alice-history"), user(session, users, "bob-history")
    alice_client, bob_client = login(alice), login(bob)
    created = alice_client.post("/api/v1/chat/sessions", headers=ORIGIN, json={})
    assert created.status_code == 201
    session_id = created.json()["id"]
    assert bob_client.get(f"/api/v1/chat/sessions/{session_id}").status_code == 404
    assert bob_client.get(f"/api/v1/chat/sessions/{session_id}/messages").status_code == 404
    assert bob_client.patch(f"/api/v1/chat/sessions/{session_id}", headers=ORIGIN, json={"title": "stolen"}).status_code == 404
    assert bob_client.delete(f"/api/v1/chat/sessions/{session_id}", headers=ORIGIN).status_code == 404


def test_explicit_document_uuid_injection_is_rejected_before_answer_service(db):
    session, users, documents = db
    alice, bob = user(session, users, "alice-scope"), user(session, users, "bob-scope")
    private = document(session, documents, "private-scope")
    DocumentAccessService(session).grant_private(alice.id, private.id)
    calls = SimpleNamespace(count=0)

    class NeverCalled:
        async def answer(self, *_args, **_kwargs):
            calls.count += 1
            raise AssertionError("generation must not run")

    app.dependency_overrides[get_answer_service] = lambda: NeverCalled()
    try:
        response = login(bob).post(
            "/answer", headers=ORIGIN,
            json={"query_text": "What is in Alice's document?", "document_ids": [str(private.id)]},
        )
        assert response.status_code == 404
        assert response.json()["detail"]["error_code"] == "RESOURCE_NOT_FOUND"
        assert calls.count == 0

        authorized = document(session, documents, "bob-authorized-scope")
        DocumentAccessService(session).grant_private(bob.id, authorized.id)
        mixed = login(bob).post(
            "/answer", headers=ORIGIN,
            json={"query_text": "Mixed scope must fail closed", "document_ids": [str(authorized.id), str(private.id)]},
        )
        assert mixed.status_code == 404
        assert calls.count == 0
    finally:
        app.dependency_overrides.pop(get_answer_service, None)


def test_dense_and_lexical_sql_exclude_alice_canary_for_bob(db):
    session, users, documents = db
    alice, bob = user(session, users, "alice-canary"), user(session, users, "bob-canary")
    private = document(session, documents, "alice-canary")
    DocumentAccessService(session).grant_private(alice.id, private.id)
    canary = "CONFIDENTIAL_ALICE_CANARY_8F712A"
    chunk = Chunk(
        document_id=private.id, legal_unit_id=None, chunk_index=0, content_text=canary,
        embedding_text=f"passage: {canary}", page_start=1, page_end=1,
        metadata_json={}, provenance_json={}, created_at=utcnow(),
    )
    session.add(chunk); session.flush()
    vector = np.zeros(768, dtype=np.float32); vector[0] = 1.0
    session.add(ChunkIndex(
        chunk_id=chunk.id, document_id=private.id, embedding=vector.tolist(),
        lexical_tsv=func.to_tsvector("simple", canary), embedding_model="intfloat/multilingual-e5-base",
        embedding_dimension=768, index_version="block3-v1",
    )); session.commit()
    repository = RetrievalRepository(session, UserRetrievalScope(bob.id))
    dense = repository.dense_search(vector, 50, ())
    lexical = repository.lexical_search(canary, 50, ())
    assert all(item.document_id != private.id for item in dense)
    assert all(item.document_id != private.id for item in lexical)
    assert canary not in " ".join(str(item.chunk_id) for item in dense + lexical)

    bob_client = login(bob)
    assert str(private.id) not in bob_client.get("/documents").text
    assert bob_client.get(f"/documents/{private.id}").status_code == 404
    assert bob_client.get(f"/api/v1/documents/{private.id}").status_code == 404
    assert bob_client.get(f"/api/v1/chunks/{chunk.id}").status_code == 404

    class FixedEmbedder:
        def encode(self, _query): return vector
    class WordCounter:
        provider = "fixture"
        tokenizer_id = "fixture"
        def count(self, value): return len(value.split())
    service = RetrievalService(session, embedder=FixedEmbedder(), repository=repository)
    results = service.retrieve(validate_request(RetrievalRequest(query_text=canary)))
    assert canary not in " ".join(item["content_text"] for item in results)
    package = ContextBuilderService(WordCounter()).build(
        request_id="canary-isolation", query_text=canary,
        retrieved_candidates=results, context_budget_tokens=4096,
    )
    assert canary not in package.context_text
    assert all(item.document_id != str(private.id) for item in package.selected_evidence)


def test_multiple_overlapping_private_canaries_never_enter_bob_pipeline(db):
    session, users, documents = db
    alice, bob = user(session, users, "alice-multi-canary"), user(session, users, "bob-multi-canary")
    vector = np.zeros(768, dtype=np.float32); vector[7] = 1.0
    private_document_ids = []
    private_chunk_ids = []
    markers = [
        f"ALICE_PRIVATE_CANARY_{uuid.uuid4().hex.upper()}",
        f"ALICE_PRIVATE_CANARY_{uuid.uuid4().hex.upper()}",
        f"ALICE_PRIVATE_CANARY_{uuid.uuid4().hex.upper()}",
    ]
    for index, marker in enumerate(markers):
        source = document(session, documents, f"overlapping-banking-topic-{index}")
        DocumentAccessService(session).grant_private(alice.id, source.id)
        chunk = Chunk(
            document_id=source.id, legal_unit_id=None, chunk_index=0,
            content_text=f"Nghĩa vụ pháp lý ngân hàng {marker}",
            embedding_text=f"passage: Nghĩa vụ pháp lý ngân hàng {marker}",
            page_start=1, page_end=1, metadata_json={}, provenance_json={}, created_at=utcnow(),
        )
        session.add(chunk); session.flush()
        session.add(ChunkIndex(
            chunk_id=chunk.id, document_id=source.id, embedding=vector.tolist(),
            lexical_tsv=func.to_tsvector("simple", chunk.content_text),
            embedding_model="intfloat/multilingual-e5-base", embedding_dimension=768, index_version="block3-v1",
        ))
        private_document_ids.append(source.id); private_chunk_ids.append(chunk.id)
    session.commit()

    repository = RetrievalRepository(session, UserRetrievalScope(bob.id))
    dense = repository.dense_search(vector, 50, ())
    lexical = repository.lexical_search("nghĩa vụ pháp lý ngân hàng", 50, ())
    assert not ({item.document_id for item in dense + lexical} & set(private_document_ids))

    class FixedEmbedder:
        def encode(self, _query): return vector
    class WordCounter:
        provider = "fixture"; tokenizer_id = "fixture"
        def count(self, value): return len(value.split())
    results = RetrievalService(session, embedder=FixedEmbedder(), repository=repository).retrieve(
        validate_request(RetrievalRequest(query_text="nghĩa vụ pháp lý ngân hàng"))
    )
    package = ContextBuilderService(WordCounter()).build(
        request_id="multi-canary-isolation",
        query_text="nghĩa vụ pháp lý ngân hàng",
        retrieved_candidates=results,
        context_budget_tokens=4096,
    )
    serialized = package.context_text + " " + " ".join(item.content_text for item in package.selected_evidence)
    assert all(marker not in serialized for marker in markers)
    assert not ({uuid.UUID(item.document_id) for item in package.selected_evidence} & set(private_document_ids))
    bob_client = login(bob)
    for document_id, chunk_id in zip(private_document_ids, private_chunk_ids):
        assert bob_client.get(f"/documents/{document_id}").status_code == 404
        assert bob_client.get(f"/api/v1/chunks/{chunk_id}").status_code == 404


def test_cross_user_dedup_and_private_global_references_are_independent(db):
    session, users, documents = db
    alice, bob, admin = user(session, users, "alice-dedup"), user(session, users, "bob-dedup"), user(session, users, "admin-dedup", UserRole.ADMIN)
    raw = Path("tests/fixtures/sample_legal.pdf").read_bytes() + f"\n% auth-dedup-{uuid.uuid4()}".encode()

    class Storage:
        def upload_pdf(self, document_id, _data): return f"minio://documents/{document_id}/original.pdf"
    class Queue:
        def enqueue_ingestion_job(self, *_args): return None

    upload = UploadService(DocumentRepository(session), JobRepository(session), Storage(), Queue())
    access = DocumentAccessService(session)
    first, _ = upload.process_upload(raw, "x.pdf", "application/pdf", on_document_resolved=lambda item: access.grant_private(alice.id, item.id))
    documents.append(first.id)
    second, second_job = upload.process_upload(raw, "x.pdf", "application/pdf", on_document_resolved=lambda item: access.grant_private(bob.id, item.id))
    assert first.id == second.id and second_job is None
    assert session.scalar(select(func.count(Document.id)).where(Document.sha256 == hashlib.sha256(raw).hexdigest())) == 1
    assert session.scalar(select(func.count(DocumentAccessGrant.document_id)).where(DocumentAccessGrant.document_id == first.id)) == 2

    access.grant_global(admin.id, first.id)
    assert access.access_origin(alice.id, first.id) == "PRIVATE + GLOBAL"
    assert access.revoke_global(first.id) is False
    assert access.access_origin(alice.id, first.id) == "PRIVATE"
    assert access.revoke_private(alice.id, first.id) is False
    assert access.access_origin(bob.id, first.id) == "PRIVATE"


def test_rbac_debug_and_evaluation_backend_authority(db, monkeypatch):
    session, users, _documents = db
    normal, admin = user(session, users, "rbac-user"), user(session, users, "rbac-admin", UserRole.ADMIN)
    monkeypatch.setattr("app.core.config.settings.DEBUG_UI_ENABLED", False)
    monkeypatch.setattr("app.core.config.settings.EVALUATION_UI_ENABLED", False)
    assert login(normal).get("/internal/debug/status").status_code == 403
    assert login(normal).get("/internal/evaluation/summary").status_code == 403
    assert login(admin).get("/internal/debug/status").status_code == 404
    assert login(admin).get("/internal/evaluation/summary").status_code == 404
    monkeypatch.setattr("app.core.config.settings.DEBUG_UI_ENABLED", True)
    monkeypatch.setattr("app.core.config.settings.EVALUATION_UI_ENABLED", True)
    assert login(normal).get("/internal/debug/status").status_code == 403
    assert login(normal).get("/internal/evaluation/summary").status_code == 403
    assert login(admin).get("/internal/evaluation/summary").status_code == 200


def test_account_deletion_202_durable_enqueue_gap_and_idempotent_worker(db, monkeypatch):
    session, users, documents = db
    alice, bob = user(session, users, "delete-alice"), user(session, users, "delete-bob")
    alice_id, bob_id = alice.id, bob.id
    unique, shared = document(session, documents, "delete-unique"), document(session, documents, "delete-shared")
    unique_id, shared_id = unique.id, shared.id
    access = DocumentAccessService(session)
    access.grant_private(alice.id, unique.id); access.grant_private(alice.id, shared.id); access.grant_private(bob.id, shared.id)
    ChatHistoryService(session, alice.id).create_session("Private history")
    client = login(alice)

    monkeypatch.setattr(auth_routes.rq_client, "enqueue_account_deletion_job", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("redis down")))
    response = client.request("DELETE", "/api/v1/auth/account", headers=ORIGIN, json={"password": PASSWORD})
    assert response.status_code == 202 and response.json()["state"] == "PENDING"
    job_id = uuid.UUID(response.json()["job_id"])
    session.expire_all()
    assert session.get(User, alice_id).status == UserStatus.DELETING.value
    assert session.get(AccountDeletionJob, job_id).state == "PENDING"
    assert client.get("/api/v1/auth/me").status_code == 401

    monkeypatch.setattr("app.auth.worker.minio_client.delete", lambda _document_id: None)
    process_account_deletion(str(job_id))
    session.expire_all()
    assert session.get(User, alice_id) is None
    assert session.get(ChatSession, ChatHistoryService(session, bob.id).create_session("Bob remains").id) is not None
    assert session.get(Document, unique_id) is None
    assert session.get(Document, shared_id) is not None
    assert session.get(DocumentAccessGrant, (shared_id, bob_id)) is not None
    assert session.get(AccountDeletionJob, job_id).state == "COMPLETED"
    users.remove(alice_id); documents.remove(unique_id)


def test_cookie_origin_policy_and_stateless_routes_require_authentication(db):
    session, users, _documents = db
    alice = user(session, users, "origin")
    client = login(alice)
    assert client.post("/api/v1/auth/logout").status_code == 403
    assert client.post("/api/v1/auth/logout", headers={"Origin": "https://evil.invalid"}).status_code == 403
    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 204

    anonymous = TestClient(app)
    calls = [
        ("post", "/retrieve", {"json": {"query_text": "test"}}),
        ("post", "/answer", {"json": {"query_text": "test"}}),
        ("post", "/answer/stream", {"json": {"query_text": "test"}}),
        ("get", "/documents", {}),
        ("get", "/api/v1/chat/sessions", {}),
        ("get", "/internal/debug/status", {}),
        ("get", "/internal/evaluation/summary", {}),
    ]
    for method, path, kwargs in calls:
        assert getattr(anonymous, method)(path, **kwargs).status_code == 401


def test_historical_snapshot_survives_global_revoke_but_current_source_is_hidden(db):
    session, users, documents = db
    bob, admin = user(session, users, "snapshot-bob"), user(session, users, "snapshot-admin", UserRole.ADMIN)
    source = document(session, documents, "snapshot-source")
    source_id = source.id
    access = DocumentAccessService(session)
    access.grant_global(admin.id, source_id)
    chunk = Chunk(
        document_id=source_id, legal_unit_id=None, chunk_index=0,
        content_text="Historical evidence snapshot text", embedding_text="passage: Historical evidence snapshot text",
        page_start=1, page_end=1, metadata_json={}, provenance_json={}, created_at=utcnow(),
    )
    session.add(chunk); session.flush()
    chat = ChatHistoryService(session, bob.id).create_session("Snapshot")
    turn = ChatTurn(
        session_id=chat.id, client_turn_id=uuid.uuid4(), request_hash="a" * 64,
        state=TurnState.COMPLETED.value, completed_at=utcnow(),
    )
    session.add(turn); session.flush()
    message = ChatMessage(
        session_id=chat.id, turn_id=turn.id, role=MessageRole.ASSISTANT.value,
        sequence_no=1, content="Saved answer [S1]", delivery_state=DeliveryState.COMPLETED.value,
        answer_status="ANSWERABLE", finalized_at=utcnow(), generation_metadata_json={},
    )
    session.add(message); session.flush()
    session.add(MessageCitationSnapshot(
        message_id=message.id, citation_label="S1", citation_order=1,
        original_document_id=source_id, original_chunk_id=chunk.id,
        document_filename=source.filename, document_sha256=source.sha256,
        chunk_content_sha256=hashlib.sha256(chunk.content_text.encode()).hexdigest(),
        evidence_text=chunk.content_text, metadata_json={}, provenance_json={}, snapshot_version=1,
    ))
    session.commit()
    chat_id, chunk_id = chat.id, chunk.id
    assert access.revoke_global(source_id) is True

    client = login(bob)
    history = client.get(f"/api/v1/chat/sessions/{chat_id}/messages")
    assert history.status_code == 200
    citation = history.json()["data"][0]["citations"][0]
    assert citation["evidence_text"] == "Historical evidence snapshot text"
    assert citation["availability"] == "SOURCE_UNAVAILABLE"
    assert client.get(f"/api/v1/chunks/{chunk_id}").status_code == 404


def test_gc_and_concurrent_grant_serialize_without_dangling_reference(db, monkeypatch):
    session, users, documents = db
    alice = user(session, users, "gc-race")
    source = document(session, documents, "gc-race-source")
    source_id, alice_id = source.id, alice.id
    locked = threading.Event()
    release = threading.Event()
    outcomes: dict[str, object] = {}

    def grant_while_holding_lock():
        worker_db = SessionLocal()
        try:
            worker_db.scalar(select(Document).where(Document.id == source_id).with_for_update())
            locked.set()
            release.wait(5)
            worker_db.add(DocumentAccessGrant(document_id=source_id, user_id=alice_id))
            worker_db.commit()
            outcomes["grant"] = True
        finally:
            worker_db.close()

    def gc_after_lock():
        locked.wait(5)
        worker_db = SessionLocal()
        try:
            outcomes["gc"] = collect_canonical_document(worker_db, source_id)
        finally:
            worker_db.close()

    monkeypatch.setattr("app.auth.worker.minio_client.delete", lambda _document_id: None)
    grant_thread = threading.Thread(target=grant_while_holding_lock)
    gc_thread = threading.Thread(target=gc_after_lock)
    grant_thread.start(); gc_thread.start()
    assert locked.wait(5)
    time.sleep(0.1)
    release.set()
    grant_thread.join(5); gc_thread.join(5)
    session.expire_all()
    assert outcomes == {"grant": True, "gc": False}
    assert session.get(Document, source_id) is not None
    assert session.get(DocumentAccessGrant, (source_id, alice_id)) is not None


def test_account_deletion_worker_resumes_from_durable_refs_after_crash(db, monkeypatch):
    session, users, documents = db
    alice = user(session, users, "crash-delete")
    first = document(session, documents, "crash-first")
    second = document(session, documents, "crash-second")
    first_id, second_id, alice_id = first.id, second.id, alice.id
    access = DocumentAccessService(session)
    access.grant_private(alice_id, first_id); access.grant_private(alice_id, second_id)
    _, principal_user = AuthService(session).resolve(login(alice).cookies.get("legal_rag_session"))
    principal, _ = AuthService(session).resolve(login(principal_user).cookies.get("legal_rag_session"))
    job = AuthService(session).request_account_deletion(principal, PASSWORD)
    job_id = job.id

    from app.auth import worker as deletion_worker
    real_collect = deletion_worker.collect_canonical_document
    attempts = {"count": 0}
    def fail_second(db_session, document_id):
        attempts["count"] += 1
        if attempts["count"] == 2:
            raise RuntimeError("simulated worker crash")
        return real_collect(db_session, document_id)
    monkeypatch.setattr("app.auth.worker.minio_client.delete", lambda _document_id: None)
    monkeypatch.setattr(deletion_worker, "collect_canonical_document", fail_second)
    with pytest.raises(RuntimeError, match="simulated worker crash"):
        process_account_deletion(str(job_id))
    session.expire_all()
    assert session.get(AccountDeletionJob, job_id).state == "FAILED"
    assert session.get(User, alice_id).status == UserStatus.DELETING.value
    assert session.scalar(text("SELECT count(*) FROM account_deletion_document_refs WHERE job_id=:job_id"), {"job_id": job_id}) == 2

    monkeypatch.setattr(deletion_worker, "collect_canonical_document", real_collect)
    process_account_deletion(str(job_id))
    session.expire_all()
    assert session.get(AccountDeletionJob, job_id).state == "COMPLETED"
    assert session.get(User, alice_id) is None
    assert session.get(Document, first_id) is None and session.get(Document, second_id) is None
    users.remove(alice_id); documents.remove(first_id); documents.remove(second_id)
