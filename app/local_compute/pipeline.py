"""Durable background document pipeline for ZKD Compute."""

from __future__ import annotations

import threading
import time

from .documents import LocalDocumentStore
from .errors import LocalComputeError, LocalComputeErrorCode
from .indexing import LocalIndexService
from .jobs import LocalJobStore
from .preparation import LocalPreparationService


class LocalDocumentPipelineWorker:
    """Run durable prepare -> index jobs outside browser HTTP requests.

    The SQLite local_jobs table is the authoritative queue. The worker is
    deliberately embedded in the ZKD Compute process for Product V1 so the end
    user does not need Redis, RQ, Docker, another Python process, or another
    service.

    V1 runs one document pipeline at a time. This is intentional because local
    embedding is normally the expensive workload and parallel E5 jobs would
    compete for the same CPU/GPU and memory.
    """

    def __init__(
        self,
        settings,
        catalog,
    ):
        self.settings = settings
        self.catalog = catalog

        self.jobs = LocalJobStore(
            catalog
        )

        self.documents = LocalDocumentStore(
            settings,
            catalog,
        )

        self.preparation = LocalPreparationService(
            settings,
            catalog,
        )

        self.indexing = LocalIndexService(
            settings,
            catalog,
        )

        self._stop_event = threading.Event()

        self._thread: threading.Thread | None = None

        self._start_lock = threading.Lock()

    @property
    def running(self) -> bool:
        return bool(
            self._thread
            and self._thread.is_alive()
        )

    def start(self) -> None:
        """Start the single embedded pipeline worker.

        Jobs interrupted by a previous process shutdown are reconciled before
        new work is claimed.
        """
        with self._start_lock:
            if self.running:
                return

            self._stop_event.clear()

            self.jobs.reconcile_interrupted()

            self._thread = threading.Thread(
                target=self._run,
                name="zkd-document-pipeline",
                daemon=True,
            )

            self._thread.start()

    def stop(
        self,
        timeout: float = 5.0,
    ) -> None:
        """Request worker shutdown.

        The thread is daemonized so a Windows process shutdown is never held
        indefinitely by a very long PDF operation.
        """
        self._stop_event.set()

        thread = self._thread

        if (
            thread
            and thread.is_alive()
        ):
            thread.join(
                timeout=timeout
            )

        self._thread = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            job = None

            try:
                job = (
                    self.jobs.claim_next_pipeline()
                )
            except Exception:
                # The queue must not kill the whole local runtime because of a
                # transient SQLite failure. Retry after the normal poll delay.
                self._stop_event.wait(
                    self.settings.pipeline_poll_seconds
                )
                continue

            if not job:
                self._stop_event.wait(
                    self.settings.pipeline_poll_seconds
                )
                continue

            try:
                self._process(job)
            except Exception:
                # _process is expected to convert failures to durable job state.
                # This is the final containment boundary so one malformed PDF
                # can never kill the background worker.
                try:
                    current = self.jobs.get(
                        job["job_id"]
                    )

                    if (
                        current
                        and current["state"]
                        in (
                            "RUNNING",
                            "QUEUED",
                            "CANCEL_REQUESTED",
                        )
                    ):
                        self.jobs.update(
                            job["job_id"],
                            "FAILED",
                            "FAILED",
                            100,
                            LocalComputeErrorCode.INTERNAL_COMPUTE_ERROR.value,
                        )
                except Exception:
                    pass

    def _process(
        self,
        job: dict,
    ) -> None:
        job_id = str(
            job["job_id"]
        )

        document_id = job.get(
            "document_id"
        )

        if not document_id:
            self.jobs.update(
                job_id,
                "FAILED",
                "FAILED",
                100,
                LocalComputeErrorCode.INVALID_REQUEST.value,
            )

            return

        if self.jobs.is_cancel_requested(
            job_id
        ):
            self.jobs.update(
                job_id,
                "CANCELLED",
                "CANCELLED",
                100,
                LocalComputeErrorCode.JOB_CANCELLED.value,
            )

            return

        document = self.documents.get(
            document_id
        )

        if not document:
            self.jobs.update(
                job_id,
                "FAILED",
                "FAILED",
                100,
                LocalComputeErrorCode.DOCUMENT_NOT_FOUND.value,
            )

            return

        state = document.get(
            "preparation_state"
        )

        artifact_id = document.get(
            "active_artifact_id"
        )

        try:
            # Case 1:
            # The previous worker finished everything but the process died just
            # before the durable pipeline row was marked successful.
            if (
                state == "INDEX_READY"
                and artifact_id
            ):
                self.jobs.attach_artifact(
                    job_id,
                    artifact_id,
                )

                self.jobs.update(
                    job_id,
                    "SUCCEEDED",
                    "INDEX_READY",
                    100,
                )

                return

            # Case 2:
            # Compute died during E5 indexing. The artifact is still safe, but
            # the partial embedding tables must never be queryable. Reset the
            # catalog gate and let LocalIndexService rebuild the index from a
            # clean state.
            if (
                state == "INDEXING"
                and artifact_id
            ):
                self._set_document_state(
                    document_id,
                    "PREPARED_NOT_INDEXED",
                    None,
                )

                state = (
                    "PREPARED_NOT_INDEXED"
                )

            # Case 3:
            # Preparation is already durable. Skip PDF parsing and continue
            # directly to batched indexing.
            if (
                state
                == "PREPARED_NOT_INDEXED"
                and artifact_id
            ):
                self.jobs.attach_artifact(
                    job_id,
                    artifact_id,
                )

                self.indexing.index_document(
                    document_id,
                    job_id=job_id,
                )

                return

            # Case 4:
            # ACCEPTED / PROCESSING / CHUNKING / VALIDATING / FAILED or another
            # incomplete preparation state. Rebuild the canonical artifact from
            # the local source PDF.
            prepared = (
                self.preparation.prepare(
                    document_id,
                    job_id=job_id,
                )
            )

            if self.jobs.is_cancel_requested(
                job_id
            ):
                raise LocalComputeError(
                    LocalComputeErrorCode.JOB_CANCELLED
                )

            prepared_artifact_id = (
                prepared.get(
                    "artifact_id"
                )
            )

            if prepared_artifact_id:
                self.jobs.attach_artifact(
                    job_id,
                    prepared_artifact_id,
                )

            self.indexing.index_document(
                document_id,
                job_id=job_id,
            )

        except LocalComputeError as exc:
            current = self.jobs.get(
                job_id
            )

            # Preparation/indexing normally update the durable job themselves.
            # Only fill the state here if execution escaped before that happened.
            if (
                current
                and current["state"]
                in (
                    "RUNNING",
                    "QUEUED",
                    "CANCEL_REQUESTED",
                )
            ):
                if (
                    exc.code
                    == LocalComputeErrorCode.JOB_CANCELLED
                ):
                    self.jobs.update(
                        job_id,
                        "CANCELLED",
                        "CANCELLED",
                        100,
                        exc.code.value,
                    )
                else:
                    self.jobs.update(
                        job_id,
                        "FAILED",
                        "FAILED",
                        100,
                        exc.code.value,
                    )

        except Exception:
            current = self.jobs.get(
                job_id
            )

            if (
                current
                and current["state"]
                in (
                    "RUNNING",
                    "QUEUED",
                    "CANCEL_REQUESTED",
                )
            ):
                self.jobs.update(
                    job_id,
                    "FAILED",
                    "FAILED",
                    100,
                    LocalComputeErrorCode.INTERNAL_COMPUTE_ERROR.value,
                )

    def _set_document_state(
        self,
        document_id: str,
        state: str,
        error_code: str | None,
    ) -> None:
        with self.catalog._connect() as connection:
            connection.execute(
                """
                UPDATE local_documents
                SET preparation_state=?,
                    last_error_code=?,
                    updated_at=?
                WHERE document_id=?
                """,
                (
                    state,
                    error_code,
                    int(time.time()),
                    document_id,
                ),
            )