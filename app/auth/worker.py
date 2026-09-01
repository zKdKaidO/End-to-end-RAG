import uuid

from sqlalchemy import delete, exists, or_, select, text, update

from app.core.logging import get_logger
from app.db.database import SessionLocal
from app.models.auth import (
    AccountDeletionDocumentRef,
    AccountDeletionDocumentState,
    AccountDeletionJob,
    AccountDeletionState,
    AuthSession,
    DocumentAccessGrant,
    GlobalDocumentAccess,
    User,
    utcnow,
)
from app.models.chat import ChatSession
from app.models.compute_control import LocalDocumentManifest
from app.models.document import Document
from app.storage.minio_client import minio_client
from app.deployment.barrier import cross_store_barrier
from app.deployment.tombstones import TombstoneStoreUnavailable, deletion_tombstone_store


logger = get_logger(__name__)


def _has_access_reference(db, document_id: uuid.UUID) -> bool:
    return bool(db.scalar(select(or_(
        exists(select(1).where(DocumentAccessGrant.document_id == document_id)),
        exists(select(1).where(GlobalDocumentAccess.document_id == document_id)),
    ))))


def collect_canonical_document(db, document_id: uuid.UUID) -> bool:
    """Lock, re-check references, and remove one truly orphaned canonical aggregate."""
    document = db.scalar(select(Document).where(Document.id == document_id).with_for_update())
    if document is None:
        db.rollback()
        return True
    if _has_access_reference(db, document_id):
        db.rollback()
        return False

    # Object removal is idempotent in MinIO. Keep the document lock until the
    # relational aggregate is deleted so grant creation serializes safely.
    minio_client.delete(str(document_id))
    params = {"document_id": document_id}
    db.execute(text("DELETE FROM indexing_jobs WHERE document_id = :document_id"), params)
    db.execute(text("DELETE FROM ingestion_jobs WHERE document_id = :document_id"), params)
    db.execute(text("DELETE FROM document_pages WHERE document_id = :document_id"), params)
    db.execute(delete(LocalDocumentManifest).where(LocalDocumentManifest.document_id == document_id))
    # Block 2 derived tables and chunk indexes already have canonical cascades.
    db.execute(delete(Document).where(Document.id == document_id))
    db.commit()
    return True


def process_document_gc(document_id: str, request_id: str | None = None):
    with cross_store_barrier(exclusive=False):
        db = SessionLocal()
        try:
            return collect_canonical_document(db, uuid.UUID(document_id))
        finally:
            db.close()


def process_account_deletion(deletion_job_id: str, request_id: str | None = None):
    if not deletion_tombstone_store.contains(deletion_job_id):
        recovery_db = SessionLocal()
        try:
            recovery_job = recovery_db.get(AccountDeletionJob, uuid.UUID(deletion_job_id))
            if recovery_job is None:
                return
            deletion_tombstone_store.record(
                str(recovery_job.subject_user_id), str(recovery_job.id), recovery_job.created_at
            )
        finally:
            recovery_db.close()
    with cross_store_barrier(exclusive=False):
        return _process_account_deletion(deletion_job_id, request_id)


def _process_account_deletion(deletion_job_id: str, request_id: str | None = None):
    db = SessionLocal()
    job_uuid = uuid.UUID(deletion_job_id)
    try:
        job = db.scalar(select(AccountDeletionJob).where(AccountDeletionJob.id == job_uuid).with_for_update())
        if job is None:
            return
        if job.state == AccountDeletionState.COMPLETED.value:
            db.rollback()
            return
        job.state = AccountDeletionState.RUNNING.value
        job.started_at = job.started_at or utcnow()
        job.attempt_count += 1
        job.failure_code = None
        job.failure_detail_safe = None
        subject_user_id = job.subject_user_id
        db.commit()

        # User-scoped privacy cleanup is repeatable and cascades the History V1 aggregate.
        db.execute(update(AuthSession).where(AuthSession.user_id == subject_user_id).values(revoked_at=utcnow()))
        db.execute(delete(ChatSession).where(ChatSession.user_id == subject_user_id))
        db.execute(delete(DocumentAccessGrant).where(DocumentAccessGrant.user_id == subject_user_id))
        db.commit()

        refs = db.scalars(
            select(AccountDeletionDocumentRef).where(AccountDeletionDocumentRef.job_id == job_uuid)
        ).all()
        for ref in refs:
            if ref.state in {AccountDeletionDocumentState.DELETED.value, AccountDeletionDocumentState.RETAINED_REFERENCED.value}:
                continue
            try:
                deleted = collect_canonical_document(db, ref.document_id)
                current = db.get(AccountDeletionDocumentRef, (job_uuid, ref.document_id))
                current.state = (
                    AccountDeletionDocumentState.DELETED.value
                    if deleted else AccountDeletionDocumentState.RETAINED_REFERENCED.value
                )
                current.failure_code = None
                current.failure_detail_safe = None
                db.commit()
            except Exception as exc:
                db.rollback()
                current = db.get(AccountDeletionDocumentRef, (job_uuid, ref.document_id))
                current.state = AccountDeletionDocumentState.FAILED.value
                current.failure_code = type(exc).__name__
                current.failure_detail_safe = "Canonical cleanup failed and may be retried."
                db.commit()
                raise

        db.execute(delete(User).where(User.id == subject_user_id))
        job = db.get(AccountDeletionJob, job_uuid)
        job.state = AccountDeletionState.COMPLETED.value
        job.completed_at = utcnow()
        db.commit()
    except Exception as exc:
        db.rollback()
        job = db.get(AccountDeletionJob, job_uuid)
        if job is not None and job.state != AccountDeletionState.COMPLETED.value:
            job.state = AccountDeletionState.FAILED.value
            job.failure_code = type(exc).__name__
            job.failure_detail_safe = "Account cleanup failed safely and remains retryable."
            db.commit()
        logger.error("account_deletion_failed", deletion_job_id=deletion_job_id, error_type=type(exc).__name__)
        raise
    finally:
        db.close()
