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
    """A deliberately small durable lifecycle. Future phases attach work handlers."""

    def __init__(self, catalog: LocalCatalog):
        self.catalog = catalog

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
        with self.catalog._connect() as connection:
            row = connection.execute(
                "SELECT job_id, state, operation, created_at, updated_at FROM local_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
        if not row:
            return None
        return dict(zip(("job_id", "state", "operation", "created_at", "updated_at"), row))
