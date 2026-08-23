from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from minio.error import S3Error
from redis import Redis
from rq.job import Job
from rq.exceptions import NoSuchJobError
from sqlalchemy import select, update

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.auth import AccountDeletionDocumentRef, AccountDeletionJob, AuthSession, DocumentAccessGrant, User, UserStatus
from app.models.document import Document
from app.models.document_processing_job import DocumentProcessingJob
from app.models.indexing_job import IndexingJob
from app.models.ingestion_job import IngestionJob
from app.queue.rq_client import rq_client
from app.repositories.indexing_job_repo import IndexingJobRepository
from app.repositories.job_repo import JobRepository
from app.repositories.processing_job_repo import ProcessingJobRepository
from app.storage.minio_client import minio_client


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _write_json(path: Path | None, data: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def reconcile_cross_store(*, backup_id: str | None = None, output: Path | None = None) -> dict:
    db = SessionLocal()
    try:
        expected_rows = db.execute(
            select(Document.id, Document.sha256, Document.storage_uri).where(Document.storage_uri.is_not(None))
        ).all()
    finally:
        db.close()

    expected_keys = {f"{row.id}/original.pdf": row for row in expected_rows}
    objects: list[dict] = []
    present = 0
    missing = 0
    mismatches = 0
    for key, row in sorted(expected_keys.items()):
        item = {
            "document_id": str(row.id),
            "expected_object_key": key,
            "expected_sha256": row.sha256,
        }
        try:
            response = minio_client.client.get_object(minio_client.bucket, key)
            digest = hashlib.sha256()
            try:
                for block in iter(lambda: response.read(1024 * 1024), b""):
                    digest.update(block)
            finally:
                response.close()
                response.release_conn()
            present += 1
            if digest.hexdigest() == row.sha256:
                item["status"] = "HEALTHY"
            else:
                item["status"] = "HASH_MISMATCH"
                item["actual_sha256"] = digest.hexdigest()
                mismatches += 1
        except S3Error as exc:
            if exc.code not in {"NoSuchKey", "NoSuchObject"}:
                raise
            item["status"] = "MISSING_OBJECT"
            missing += 1
        objects.append(item)

    actual_keys = {
        item.object_name
        for item in minio_client.client.list_objects(minio_client.bucket, recursive=True)
    }
    orphan_rows = [
        {"object_key": key, "status": "ORPHAN_OBJECT"}
        for key in sorted(actual_keys - set(expected_keys))
    ]
    report = {
        "reconciliation_format_version": 1,
        "backup_id": backup_id,
        "verified_at": _utcnow().isoformat(),
        "expected_object_count": len(expected_keys),
        "present_count": present,
        "missing_count": missing,
        "hash_mismatch_count": mismatches,
        "orphan_count": len(orphan_rows),
        "objects": objects,
        "orphans": orphan_rows,
        "readiness_blocked": bool(missing or mismatches),
    }
    _write_json(output, report)
    latest = Path(settings.RECOVERY_CONTROL_DIR).resolve() / "reconciliation-latest.json"
    _write_json(latest, report)
    return report


def _rq_status(redis: Redis, job_id: str) -> tuple[bool, str | None, bool]:
    try:
        job = Job.fetch(job_id, connection=redis)
        status = job.get_status(refresh=True)
        return True, status, status in {"queued", "started", "deferred", "scheduled"}
    except NoSuchJobError:
        return False, None, False


def _discard_stale_rq_job(redis: Redis, job_id: str) -> None:
    """Remove stale RQ metadata before a deterministic DB-driven decision.

    RQ can retain a job in StartedJobRegistry after abrupt Redis/worker
    recovery. Presence alone is therefore not proof of live execution.
    """
    try:
        job = Job.fetch(job_id, connection=redis)
    except NoSuchJobError:
        return
    job.delete(delete_dependents=False)


def _stale(value: datetime | None, *, now: datetime, seconds: int) -> bool:
    aware = _aware(value)
    return aware is None or aware <= now - timedelta(seconds=seconds)


def reconcile_durable_jobs(*, output: Path | None = None, now: datetime | None = None) -> dict:
    now = now or _utcnow()
    redis = Redis.from_url(settings.REDIS_URL)
    redis.ping()
    db = SessionLocal()
    results: list[dict] = []
    try:
        specs = (
            ("INGESTION", IngestionJob, rq_client.enqueue_ingestion_job),
            ("PROCESSING", DocumentProcessingJob, rq_client.enqueue_document_processing_job),
            ("INDEXING", IndexingJob, rq_client.enqueue_indexing_job),
        )
        for job_type, model, enqueue in specs:
            jobs = db.scalars(select(model).where(model.status.in_(("PENDING", "PROCESSING")))).all()
            for job in jobs:
                exists, rq_state, live = _rq_status(redis, str(job.id))
                stale_basis = getattr(job, "started_at", None) or getattr(job, "created_at", None)
                stale = job.status == "PROCESSING" and _stale(
                    stale_basis, now=now, seconds=settings.RECOVERY_JOB_STALE_SECONDS
                )
                action = "NO_ACTION"
                if live and not stale:
                    action = "KEEP"
                elif job.status == "PENDING":
                    if exists:
                        _discard_stale_rq_job(redis, str(job.id))
                    if job_type == "INDEXING":
                        enqueue(str(job.id), str(job.document_id), None)
                    else:
                        enqueue(str(job.id), str(job.document_id), None)
                    action = "REQUEUE"
                elif stale:
                    if exists:
                        _discard_stale_rq_job(redis, str(job.id))
                    safe = "Queue execution state was lost during recovery. Explicit retry is allowed."
                    stage = getattr(job, "current_stage", None) or "RECOVERY"
                    if job_type == "INGESTION":
                        JobRepository(db).mark_failed(str(job.id), stage, "SYSTEM_RESTART_QUEUE_LOST", safe)
                    elif job_type == "PROCESSING":
                        ProcessingJobRepository(db).mark_failed(str(job.id), stage, "SYSTEM_RESTART_QUEUE_LOST", safe)
                    else:
                        IndexingJobRepository(db).mark_failed(str(job.id), stage, "SYSTEM_RESTART_QUEUE_LOST", safe)
                    action = "FAILED"
                results.append({
                    "job_type": job_type,
                    "durable_db_id": str(job.id),
                    "db_state": job.status,
                    "rq_presence": exists,
                    "rq_state": rq_state,
                    "stale": stale,
                    "action": action,
                })

        deletion_jobs = db.scalars(
            select(AccountDeletionJob).where(AccountDeletionJob.state.in_(("PENDING", "QUEUED", "RUNNING", "FAILED")))
        ).all()
        for job in deletion_jobs:
            exists, rq_state, live = _rq_status(redis, str(job.id))
            stale = job.state == "RUNNING" and _stale(
                job.started_at, now=now, seconds=settings.RECOVERY_JOB_STALE_SECONDS
            )
            action = "KEEP" if live and not stale else "NO_ACTION"
            if (not live or stale) and (job.state in {"PENDING", "QUEUED", "FAILED"} or stale):
                if exists:
                    _discard_stale_rq_job(redis, str(job.id))
                if stale:
                    job.state = "FAILED"
                    job.failure_code = "SYSTEM_RESTART_QUEUE_LOST"
                    job.failure_detail_safe = "Deletion execution was interrupted and will be retried."
                    db.commit()
                rq_client.enqueue_account_deletion_job(str(job.id))
                job.state = "QUEUED"
                db.commit()
                action = "REQUEUE"
            results.append({
                "job_type": "ACCOUNT_DELETION",
                "durable_db_id": str(job.id),
                "db_state": job.state,
                "rq_presence": exists,
                "rq_state": rq_state,
                "stale": stale,
                "action": action,
            })
    finally:
        db.close()

    report = {
        "job_reconciliation_format_version": 1,
        "verified_at": now.isoformat(),
        "results": results,
        "counts": {action: sum(1 for row in results if row["action"] == action) for action in ("KEEP", "REQUEUE", "FAILED", "NO_ACTION")},
        "redis_backup_required": False,
        "chat_turn_recovery": "EXISTING_HISTORY_V1_UNCHANGED",
    }
    _write_json(output, report)
    return report


def revoke_all_auth_sessions() -> int:
    db = SessionLocal()
    try:
        result = db.execute(update(AuthSession).where(AuthSession.revoked_at.is_(None)).values(revoked_at=_utcnow()))
        db.commit()
        return int(result.rowcount or 0)
    finally:
        db.close()


def replay_deletion_tombstones(tombstones: list, *, enqueue: bool = True) -> dict:
    db = SessionLocal()
    replayed: list[dict] = []
    try:
        for item in tombstones:
            user_id = uuid.UUID(item.subject_user_id)
            job_id = uuid.UUID(item.account_deletion_job_id)
            user = db.get(User, user_id)
            if user is None:
                replayed.append({"subject_user_id": str(user_id), "action": "ALREADY_ABSENT"})
                continue
            user.status = UserStatus.DELETING.value
            db.execute(update(AuthSession).where(AuthSession.user_id == user_id).values(revoked_at=_utcnow()))
            job = db.get(AccountDeletionJob, job_id)
            if job is None:
                job = AccountDeletionJob(
                    id=job_id,
                    subject_user_id=user_id,
                    state="PENDING",
                    created_at=datetime.fromisoformat(item.deletion_requested_at),
                    attempt_count=0,
                )
                db.add(job)
                db.flush()
                document_ids = db.scalars(
                    select(DocumentAccessGrant.document_id).where(DocumentAccessGrant.user_id == user_id)
                ).all()
                db.add_all([
                    AccountDeletionDocumentRef(job_id=job_id, document_id=document_id, state="PENDING")
                    for document_id in document_ids
                ])
            db.commit()
            if enqueue:
                rq_client.enqueue_account_deletion_job(str(job_id))
                job.state = "QUEUED"
                db.commit()
            replayed.append({"subject_user_id": str(user_id), "job_id": str(job_id), "action": "REPLAYED"})
    finally:
        db.close()
    return {"replayed": replayed, "count": len(replayed)}
