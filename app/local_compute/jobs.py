"""Durable local job-state foundation; it does not execute RAG work."""

from __future__ import annotations

import time
import uuid
from enum import Enum

from .catalog import LocalCatalog


class LocalJobState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"


class LocalJobStore:
    def __init__(self, catalog: LocalCatalog):
        self.catalog = catalog

    def enqueue_preparation(self, document_id: str, artifact_id: str) -> str:
        job_id, now = str(uuid.uuid4()), int(time.time())
        with self.catalog._connect() as connection:
            connection.execute("INSERT INTO local_jobs(job_id,state,operation,document_id,artifact_id,stage,progress,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)", (job_id, "QUEUED", "PREPARE_DOCUMENT", document_id, artifact_id, "ACCEPTED", 0, now, now))
        return job_id

    def enqueue_skeleton(self, operation: str) -> str:
        job_id = str(uuid.uuid4())
        now = int(time.time())
        with self.catalog._connect() as connection:
            connection.execute(
                "INSERT INTO local_jobs(job_id, state, operation, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (job_id, LocalJobState.QUEUED.value, operation, now, now),
            )
        return job_id

    def get(self, job_id: str) -> dict | None:
        fields = ("job_id","state","operation","document_id","artifact_id","stage","progress","error_code","cancellation_requested","created_at","updated_at")
        with self.catalog._connect() as connection:
            row = connection.execute(f"SELECT {','.join(fields)} FROM local_jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row:
            return None
        return dict(zip(fields, row))

    def update(self, job_id: str, state: str, stage: str, progress: int, error_code: str | None = None) -> None:
        with self.catalog._connect() as connection:
            connection.execute("UPDATE local_jobs SET state=?,stage=?,progress=?,error_code=?,updated_at=? WHERE job_id=?", (state, stage, progress, error_code, int(time.time()), job_id))

    def request_cancel(self, job_id: str) -> bool:
        with self.catalog._connect() as connection:
            result = connection.execute("UPDATE local_jobs SET state='CANCEL_REQUESTED',cancellation_requested=1,updated_at=? WHERE job_id=? AND state IN ('QUEUED','RUNNING')", (int(time.time()), job_id))
        return result.rowcount == 1

    def is_cancel_requested(self, job_id: str) -> bool:
        with self.catalog._connect() as connection:
            row = connection.execute("SELECT cancellation_requested FROM local_jobs WHERE job_id=?", (job_id,)).fetchone()
        return bool(row and row[0])

    def reconcile_interrupted(self) -> int:
        with self.catalog._connect() as connection:
            result = connection.execute("UPDATE local_jobs SET state='FAILED',stage='FAILED_INTERRUPTED',error_code='PREPARATION_INTERRUPTED',updated_at=? WHERE state IN ('RUNNING','CANCEL_REQUESTED')", (int(time.time()),))
        return result.rowcount
