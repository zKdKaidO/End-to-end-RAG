"""Durable local job queue for ZKD Compute document processing."""

from __future__ import annotations

import time
import uuid
from enum import Enum

from .catalog import LocalCatalog


PROCESS_DOCUMENT = "PROCESS_DOCUMENT"
PREPARE_DOCUMENT = "PREPARE_DOCUMENT"
INDEX_DOCUMENT = "INDEX_DOCUMENT"


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

    def enqueue_pipeline(self, document_id: str) -> str:
        """Create one durable prepare -> index pipeline for a document.

        This operation is idempotent while a pipeline for the same document is
        already active. Repeated browser clicks therefore do not create several
        competing indexing jobs.
        """
        now = int(time.time())

        with self.catalog._connect() as connection:
            existing = connection.execute(
                """
                SELECT job_id
                FROM local_jobs
                WHERE document_id=?
                  AND operation=?
                  AND state IN ('QUEUED', 'RUNNING', 'CANCEL_REQUESTED')
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (
                    document_id,
                    PROCESS_DOCUMENT,
                ),
            ).fetchone()

            if existing:
                return str(existing[0])

            job_id = str(uuid.uuid4())

            connection.execute(
                """
                INSERT INTO local_jobs(
                    job_id,
                    state,
                    operation,
                    document_id,
                    artifact_id,
                    stage,
                    progress,
                    error_code,
                    cancellation_requested,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, NULL, ?, ?, NULL, 0, ?, ?)
                """,
                (
                    job_id,
                    LocalJobState.QUEUED.value,
                    PROCESS_DOCUMENT,
                    document_id,
                    "ACCEPTED",
                    0,
                    now,
                    now,
                ),
            )

        return job_id

    def enqueue_preparation(
        self,
        document_id: str,
        artifact_id: str,
    ) -> str:
        """Backward-compatible preparation job creation."""
        job_id = str(uuid.uuid4())
        now = int(time.time())

        with self.catalog._connect() as connection:
            connection.execute(
                """
                INSERT INTO local_jobs(
                    job_id,
                    state,
                    operation,
                    document_id,
                    artifact_id,
                    stage,
                    progress,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    LocalJobState.QUEUED.value,
                    PREPARE_DOCUMENT,
                    document_id,
                    artifact_id,
                    "ACCEPTED",
                    0,
                    now,
                    now,
                ),
            )

        return job_id

    def enqueue_skeleton(
        self,
        operation: str,
    ) -> str:
        """Backward-compatible generic job creation."""
        job_id = str(uuid.uuid4())
        now = int(time.time())

        with self.catalog._connect() as connection:
            connection.execute(
                """
                INSERT INTO local_jobs(
                    job_id,
                    state,
                    operation,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    LocalJobState.QUEUED.value,
                    operation,
                    now,
                    now,
                ),
            )

        return job_id

    def get(
        self,
        job_id: str,
    ) -> dict | None:
        fields = (
            "job_id",
            "state",
            "operation",
            "document_id",
            "artifact_id",
            "stage",
            "progress",
            "error_code",
            "cancellation_requested",
            "created_at",
            "updated_at",
        )

        with self.catalog._connect() as connection:
            row = connection.execute(
                f"""
                SELECT {','.join(fields)}
                FROM local_jobs
                WHERE job_id=?
                """,
                (job_id,),
            ).fetchone()

        if not row:
            return None

        return dict(zip(fields, row))

    def latest_for_document(
        self,
        document_id: str,
    ) -> dict | None:
        fields = (
            "job_id",
            "state",
            "operation",
            "document_id",
            "artifact_id",
            "stage",
            "progress",
            "error_code",
            "cancellation_requested",
            "created_at",
            "updated_at",
        )

        with self.catalog._connect() as connection:
            row = connection.execute(
                f"""
                SELECT {','.join(fields)}
                FROM local_jobs
                WHERE document_id=?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (document_id,),
            ).fetchone()

        if not row:
            return None

        return dict(zip(fields, row))

    def update(
        self,
        job_id: str,
        state: str,
        stage: str,
        progress: int,
        error_code: str | None = None,
    ) -> None:
        bounded_progress = max(
            0,
            min(100, int(progress)),
        )

        with self.catalog._connect() as connection:
            connection.execute(
                """
                UPDATE local_jobs
                SET state=?,
                    stage=?,
                    progress=?,
                    error_code=?,
                    updated_at=?
                WHERE job_id=?
                """,
                (
                    state,
                    stage,
                    bounded_progress,
                    error_code,
                    int(time.time()),
                    job_id,
                ),
            )

    def attach_artifact(
        self,
        job_id: str,
        artifact_id: str,
    ) -> None:
        with self.catalog._connect() as connection:
            connection.execute(
                """
                UPDATE local_jobs
                SET artifact_id=?,
                    updated_at=?
                WHERE job_id=?
                """,
                (
                    artifact_id,
                    int(time.time()),
                    job_id,
                ),
            )

    def claim_next_pipeline(
        self,
    ) -> dict | None:
        """Atomically claim the oldest queued document pipeline."""
        fields = (
            "job_id",
            "state",
            "operation",
            "document_id",
            "artifact_id",
            "stage",
            "progress",
            "error_code",
            "cancellation_requested",
            "created_at",
            "updated_at",
        )

        with self.catalog._connect() as connection:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            row = connection.execute(
                f"""
                SELECT {','.join(fields)}
                FROM local_jobs
                WHERE state='QUEUED'
                  AND operation=?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (PROCESS_DOCUMENT,),
            ).fetchone()

            if not row:
                connection.commit()
                return None

            job = dict(zip(fields, row))

            result = connection.execute(
                """
                UPDATE local_jobs
                SET state='RUNNING',
                    stage=CASE
                        WHEN stage='RECOVERING'
                            THEN 'RECOVERING'
                        ELSE 'STARTING'
                    END,
                    updated_at=?
                WHERE job_id=?
                  AND state='QUEUED'
                """,
                (
                    int(time.time()),
                    job["job_id"],
                ),
            )

            if result.rowcount != 1:
                connection.rollback()
                return None

            connection.commit()

        job["state"] = LocalJobState.RUNNING.value
        job["stage"] = (
            "RECOVERING"
            if job["stage"] == "RECOVERING"
            else "STARTING"
        )

        return job

    def request_cancel(
        self,
        job_id: str,
    ) -> bool:
        with self.catalog._connect() as connection:
            result = connection.execute(
                """
                UPDATE local_jobs
                SET state='CANCEL_REQUESTED',
                    cancellation_requested=1,
                    updated_at=?
                WHERE job_id=?
                  AND state IN ('QUEUED', 'RUNNING')
                """,
                (
                    int(time.time()),
                    job_id,
                ),
            )

        return result.rowcount == 1

    def is_cancel_requested(
        self,
        job_id: str,
    ) -> bool:
        with self.catalog._connect() as connection:
            row = connection.execute(
                """
                SELECT cancellation_requested
                FROM local_jobs
                WHERE job_id=?
                """,
                (job_id,),
            ).fetchone()

        return bool(row and row[0])

    def cancel_for_document(
        self,
        document_id: str,
    ) -> int:
        with self.catalog._connect() as connection:
            result = connection.execute(
                """
                UPDATE local_jobs
                SET state='CANCEL_REQUESTED',
                    cancellation_requested=1,
                    updated_at=?
                WHERE document_id=?
                  AND state IN ('QUEUED', 'RUNNING')
                """,
                (
                    int(time.time()),
                    document_id,
                ),
            )

        return result.rowcount

    def reconcile_interrupted(
        self,
    ) -> int:
        """Recover jobs left behind by an interrupted Compute process.

        New PROCESS_DOCUMENT jobs are returned to the durable queue rather than
        permanently failed. Legacy synchronous jobs retain fail-closed behavior.
        """
        now = int(time.time())
        affected = 0

        with self.catalog._connect() as connection:
            cancelled = connection.execute(
                """
                UPDATE local_jobs
                SET state='CANCELLED',
                    stage='CANCELLED',
                    progress=100,
                    updated_at=?
                WHERE operation=?
                  AND state IN ('RUNNING', 'CANCEL_REQUESTED')
                  AND cancellation_requested=1
                """,
                (
                    now,
                    PROCESS_DOCUMENT,
                ),
            )

            affected += cancelled.rowcount

            recoverable = connection.execute(
                """
                UPDATE local_jobs
                SET state='QUEUED',
                    stage='RECOVERING',
                    error_code=NULL,
                    cancellation_requested=0,
                    updated_at=?
                WHERE operation=?
                  AND state IN ('RUNNING', 'CANCEL_REQUESTED')
                  AND cancellation_requested=0
                """,
                (
                    now,
                    PROCESS_DOCUMENT,
                ),
            )

            affected += recoverable.rowcount

            legacy = connection.execute(
                """
                UPDATE local_jobs
                SET state='FAILED',
                    stage='FAILED_INTERRUPTED',
                    error_code='PREPARATION_INTERRUPTED',
                    updated_at=?
                WHERE operation<>?
                  AND state IN ('RUNNING', 'CANCEL_REQUESTED')
                """,
                (
                    now,
                    PROCESS_DOCUMENT,
                ),
            )

            affected += legacy.rowcount

        return affected