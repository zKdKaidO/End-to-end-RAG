from sqlalchemy import exists, or_, select, update

from app.db.database import SessionLocal
from app.models.auth import AccountDeletionJob, DocumentAccessGrant, GlobalDocumentAccess
from app.models.document import Document
from app.queue.rq_client import rq_client
from app.deployment.tombstones import TombstoneStoreUnavailable, deletion_tombstone_store


def reconcile_durable_cleanup_intents() -> None:
    db = SessionLocal()
    try:
        jobs = db.scalars(select(AccountDeletionJob.id).where(AccountDeletionJob.state.in_(("PENDING", "FAILED")))).all()
        for job_id in jobs:
            try:
                job = db.get(AccountDeletionJob, job_id)
                deletion_tombstone_store.record(str(job.subject_user_id), str(job.id), job.created_at)
                rq_client.enqueue_account_deletion_job(str(job_id))
                db.execute(
                    update(AccountDeletionJob)
                    .where(
                        AccountDeletionJob.id == job_id,
                        AccountDeletionJob.state.in_(("PENDING", "FAILED")),
                    )
                    .values(state="QUEUED")
                )
                db.commit()
            except Exception:
                db.rollback()

        orphan_ids = db.scalars(
            select(Document.id).where(~or_(
                exists(select(1).where(DocumentAccessGrant.document_id == Document.id)),
                exists(select(1).where(GlobalDocumentAccess.document_id == Document.id)),
            )).limit(100)
        ).all()
        for document_id in orphan_ids:
            try:
                rq_client.enqueue_document_gc(str(document_id))
            except Exception:
                pass
    finally:
        db.close()
