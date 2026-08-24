import hashlib
import threading
import time
import uuid

import pytest
from redis import Redis
from rq.registry import FailedJobRegistry
from sqlalchemy import delete, func, select, text

from app.auth.access import DocumentAccessService
from app.auth.principal import Principal
from app.auth.service import AuthService
from app.auth.worker import collect_canonical_document, process_account_deletion
from app.core.config import settings
from app.db.database import SessionLocal
from app.models.auth import AccountDeletionJob, DocumentAccessGrant, User, UserRole
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus
from app.models.document_page import DocumentPage
from app.models.document_processing_job import DocumentProcessingJob
from app.models.document_reconstruction import DocumentReconstruction
from app.models.legal_unit import LegalUnit
from app.processing_worker_main import process_document
from app.repositories.processing_job_repo import ProcessingJobRepository


PASSWORD = "correct horse battery staple"


@pytest.fixture
def lifecycle_fixture(monkeypatch):
    session = SessionLocal()
    user_ids: list[uuid.UUID] = []
    document_ids: list[uuid.UUID] = []
    monkeypatch.setattr("app.auth.worker.minio_client.delete", lambda _document_id: None)
    yield session, user_ids, document_ids
    session.rollback()
    cleanup = SessionLocal()
    try:
        if user_ids:
            cleanup.execute(delete(AccountDeletionJob).where(AccountDeletionJob.subject_user_id.in_(user_ids)))
            cleanup.execute(delete(DocumentAccessGrant).where(DocumentAccessGrant.user_id.in_(user_ids)))
        if document_ids:
            params = {"ids": [str(value) for value in document_ids]}
            cleanup.execute(text("DELETE FROM indexing_jobs WHERE document_id = ANY(CAST(:ids AS uuid[]))"), params)
            cleanup.execute(text("DELETE FROM ingestion_jobs WHERE document_id = ANY(CAST(:ids AS uuid[]))"), params)
            cleanup.execute(text("DELETE FROM document_pages WHERE document_id = ANY(CAST(:ids AS uuid[]))"), params)
            cleanup.execute(delete(Document).where(Document.id.in_(document_ids)))
        if user_ids:
            cleanup.execute(delete(User).where(User.id.in_(user_ids)))
        cleanup.commit()
    finally:
        cleanup.close()
        session.close()


def _user(session, user_ids, name: str):
    user = AuthService(session).provision_user(
        f"processing-race-{name}-{uuid.uuid4()}@example.invalid",
        PASSWORD,
        UserRole.USER,
        must_change_password=False,
    )
    user_ids.append(user.id)
    return user


def _target(session, document_ids, *users):
    marker = f"PROCESSING_LIFECYCLE_{uuid.uuid4().hex.upper()}"
    document = Document(
        filename=f"{marker}.pdf",
        mime_type="application/pdf",
        file_size=1024,
        sha256=hashlib.sha256(marker.encode()).hexdigest(),
        status=DocumentStatus.COMPLETED,
    )
    session.add(document)
    session.flush()
    session.add(DocumentPage(
        document_id=document.id,
        page_number=1,
        raw_text=f"Điều 1. Phạm vi. {marker} có thời hạn hỗ trợ là 37 ngày.",
        char_count=80,
    ))
    session.commit()
    document_ids.append(document.id)
    access = DocumentAccessService(session)
    for user in users:
        access.grant_private(user.id, document.id)
    job = ProcessingJobRepository(session).create_job(str(document.id))
    return document.id, job.id


def _run_worker(document_id, job_id, outcomes):
    try:
        outcomes["result"] = process_document(str(job_id), str(document_id), "processing-race-test")
    except BaseException as exc:  # captured for deterministic thread assertion
        outcomes["exception"] = exc


def _assert_no_derived(session, document_id):
    session.expire_all()
    assert session.get(Document, document_id) is None
    assert session.scalar(select(func.count(DocumentReconstruction.id)).where(DocumentReconstruction.document_id == document_id)) == 0
    assert session.scalar(select(func.count(LegalUnit.id)).where(LegalUnit.document_id == document_id)) == 0
    assert session.scalar(select(func.count(Chunk.id)).where(Chunk.document_id == document_id)) == 0


def _assert_not_failed(job_id):
    registry = FailedJobRegistry("document-processing", connection=Redis.from_url(settings.REDIS_URL))
    assert str(job_id) not in registry.get_job_ids()


def _before_persistence_barrier(monkeypatch):
    reached = threading.Event()
    release = threading.Event()

    def hook(phase, _document_id, _job_id):
        if phase == "BEFORE_PERSISTENCE":
            reached.set()
            assert release.wait(10), "test did not release pre-persistence barrier"

    monkeypatch.setattr("app.processing_worker_main.LIFECYCLE_TEST_HOOK", hook)
    return reached, release


def test_document_delete_wins_before_processing_persistence(lifecycle_fixture, monkeypatch):
    session, user_ids, document_ids = lifecycle_fixture
    alice = _user(session, user_ids, "document-delete")
    document_id, job_id = _target(session, document_ids, alice)
    reached, release = _before_persistence_barrier(monkeypatch)
    outcomes = {}
    worker = threading.Thread(target=_run_worker, args=(document_id, job_id, outcomes))
    worker.start()
    assert reached.wait(10)

    assert DocumentAccessService(session).revoke_private(alice.id, document_id) is True
    gc_db = SessionLocal()
    try:
        assert collect_canonical_document(gc_db, document_id) is True
    finally:
        gc_db.close()
    release.set()
    worker.join(10)

    assert not worker.is_alive()
    assert outcomes.get("exception") is None
    _assert_no_derived(session, document_id)
    _assert_not_failed(job_id)


def test_account_delete_unique_canonical_wins_before_processing_persistence(lifecycle_fixture, monkeypatch):
    session, user_ids, document_ids = lifecycle_fixture
    alice = _user(session, user_ids, "account-unique")
    alice_id = alice.id
    document_id, job_id = _target(session, document_ids, alice)
    reached, release = _before_persistence_barrier(monkeypatch)
    outcomes = {}
    worker = threading.Thread(target=_run_worker, args=(document_id, job_id, outcomes))
    worker.start()
    assert reached.wait(10)

    deletion_job = AuthService(session).request_account_deletion(
        Principal(user_id=alice_id, role=UserRole.USER.value, auth_session_id=uuid.uuid4()),
        PASSWORD,
    )
    process_account_deletion(str(deletion_job.id), "processing-race-test")
    release.set()
    worker.join(10)

    assert not worker.is_alive()
    assert outcomes.get("exception") is None
    session.expire_all()
    assert session.get(User, alice_id) is None
    _assert_no_derived(session, document_id)
    _assert_not_failed(job_id)


def test_account_delete_shared_canonical_keeps_processing_for_remaining_grant(lifecycle_fixture, monkeypatch):
    session, user_ids, document_ids = lifecycle_fixture
    alice = _user(session, user_ids, "account-shared-alice")
    bob = _user(session, user_ids, "account-shared-bob")
    alice_id, bob_id = alice.id, bob.id
    document_id, job_id = _target(session, document_ids, alice, bob)
    reached, release = _before_persistence_barrier(monkeypatch)
    monkeypatch.setattr("app.processing_worker_main.enqueue_canonical_indexing", lambda *_args: object())
    outcomes = {}
    worker = threading.Thread(target=_run_worker, args=(document_id, job_id, outcomes))
    worker.start()
    assert reached.wait(10)

    deletion_job = AuthService(session).request_account_deletion(
        Principal(user_id=alice_id, role=UserRole.USER.value, auth_session_id=uuid.uuid4()),
        PASSWORD,
    )
    process_account_deletion(str(deletion_job.id), "processing-race-test")
    release.set()
    worker.join(10)

    assert not worker.is_alive()
    assert outcomes.get("exception") is None
    session.expire_all()
    assert session.get(User, alice_id) is None
    assert session.get(Document, document_id) is not None
    assert session.get(DocumentAccessGrant, (document_id, bob_id)) is not None
    assert DocumentAccessService(session).is_accessible(bob_id, document_id) is True
    assert session.get(DocumentProcessingJob, job_id).status == "COMPLETED"
    assert session.scalar(select(func.count(DocumentReconstruction.id)).where(DocumentReconstruction.document_id == document_id)) == 1
    assert session.scalar(select(func.count(Chunk.id)).where(Chunk.document_id == document_id)) > 0
    _assert_not_failed(job_id)


def test_processing_persistence_lock_wins_and_gc_serializes(lifecycle_fixture, monkeypatch):
    session, user_ids, document_ids = lifecycle_fixture
    alice = _user(session, user_ids, "worker-wins")
    document_id, job_id = _target(session, document_ids, alice)
    assert DocumentAccessService(session).revoke_private(alice.id, document_id) is True

    locked = threading.Event()
    release = threading.Event()

    def persistence_hook(phase, _document_id, _job_id):
        if phase == "PERSISTENCE_LOCKED":
            locked.set()
            assert release.wait(10), "test did not release persistence lock barrier"

    monkeypatch.setattr("app.repositories.processing_repo.LIFECYCLE_TEST_HOOK", persistence_hook)
    monkeypatch.setattr(
        "app.processing_worker_main.enqueue_canonical_indexing",
        lambda *_args: (_ for _ in ()).throw(AssertionError("unreferenced target must not be indexed")),
    )
    worker_outcome = {}
    worker = threading.Thread(target=_run_worker, args=(document_id, job_id, worker_outcome))
    worker.start()
    assert locked.wait(10)

    gc_outcome = {}
    gc_started = threading.Event()

    def run_gc():
        gc_db = SessionLocal()
        try:
            gc_db.execute(text("SET application_name = 'processing-race-gc-waiter'"))
            gc_started.set()
            gc_outcome["deleted"] = collect_canonical_document(gc_db, document_id)
        except BaseException as exc:
            gc_outcome["exception"] = exc
        finally:
            gc_db.close()

    gc = threading.Thread(target=run_gc)
    gc.start()
    assert gc_started.wait(10)

    inspector = SessionLocal()
    try:
        deadline = time.monotonic() + 10
        waiter_observed = False
        while time.monotonic() < deadline:
            waiter_observed = bool(inspector.scalar(text(
                "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                "WHERE application_name='processing-race-gc-waiter' AND wait_event_type='Lock')"
            )))
            inspector.rollback()
            if waiter_observed:
                break
            threading.Event().wait(0.02)
        assert waiter_observed, "GC never reached the canonical lifecycle lock wait"
    finally:
        inspector.close()

    release.set()
    worker.join(10)
    gc.join(10)

    assert not worker.is_alive() and not gc.is_alive()
    assert worker_outcome.get("exception") is None
    assert gc_outcome == {"deleted": True}
    _assert_no_derived(session, document_id)
    _assert_not_failed(job_id)
