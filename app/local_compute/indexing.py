"""Canonical batched E5 indexing for a prepared local artifact."""

from __future__ import annotations

import math
import sqlite3
import time

import numpy as np

from app.indexing.embedder import E5Embedder

from .errors import LocalComputeError, LocalComputeErrorCode
from .jobs import LocalJobStore


INDEX_VERSION = "block3-v1"
EMBEDDING_DIMENSION = 768
EMBEDDING_BYTES = EMBEDDING_DIMENSION * 4


class LocalIndexService:
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

    def index_document(
        self,
        document_id: str,
        job_id: str | None = None,
    ) -> dict:
        """Index one prepared document.

        job_id=None preserves the previous standalone indexing contract.

        When a PROCESS_DOCUMENT job_id is supplied, indexing continues that
        durable pipeline and owns progress 60..100.
        """
        with self.catalog.document_lock(
            document_id
        ):
            return self._index_document_locked(
                document_id,
                job_id=job_id,
            )

    def _index_document_locked(
        self,
        document_id: str,
        job_id: str | None = None,
    ) -> dict:
        document = self._document(
            document_id
        )

        if document[
            "preparation_state"
        ] not in (
            "PREPARED_NOT_INDEXED",
            "INDEX_READY",
        ):
            raise LocalComputeError(
                LocalComputeErrorCode.CAPABILITY_UNAVAILABLE,
                "Document is not prepared for indexing.",
            )

        artifact_id = document[
            "active_artifact_id"
        ]

        if not artifact_id:
            raise LocalComputeError(
                LocalComputeErrorCode.CAPABILITY_UNAVAILABLE,
                "Prepared document has no active artifact.",
            )

        pipeline_job = (
            job_id is not None
        )

        if job_id is None:
            job_id = (
                self.jobs.enqueue_skeleton(
                    "INDEX_DOCUMENT"
                )
            )

            with self.catalog._connect() as connection:
                connection.execute(
                    """
                    UPDATE local_jobs
                    SET document_id=?,
                        artifact_id=?,
                        stage='INDEXING',
                        state='RUNNING',
                        progress=0,
                        updated_at=?
                    WHERE job_id=?
                    """,
                    (
                        document_id,
                        artifact_id,
                        int(time.time()),
                        job_id,
                    ),
                )
        else:
            job = self.jobs.get(
                job_id
            )

            if (
                not job
                or job.get(
                    "document_id"
                )
                != document_id
            ):
                raise LocalComputeError(
                    LocalComputeErrorCode.INVALID_REQUEST,
                    "Indexing job does not belong to the document.",
                )

            self.jobs.attach_artifact(
                job_id,
                artifact_id,
            )

        with self.catalog._connect() as connection:
            connection.execute(
                """
                UPDATE local_documents
                SET preparation_state='INDEXING',
                    last_error_code=NULL,
                    updated_at=?
                WHERE document_id=?
                """,
                (
                    int(time.time()),
                    document_id,
                ),
            )

        try:
            self._cancel_if_requested(
                job_id
            )

            self._update_job(
                job_id,
                "RUNNING",
                "LOADING_EMBEDDING_MODEL",
                5,
                pipeline_job,
            )

            try:
                embedder = (
                    E5Embedder.get_instance(
                        cache_dir=str(
                            self.settings.embedding_model_cache_dir
                        ),
                        device="cpu",
                    )
                )
            except Exception as exc:
                raise LocalComputeError(
                    LocalComputeErrorCode.MODEL_ARTIFACT_UNAVAILABLE,
                    "Canonical E5 embedding model is unavailable.",
                    diagnostic_code="model_load_failed",
                ) from exc

            self._cancel_if_requested(
                job_id
            )

            artifact_path = (
                self.settings.data_root
                / self._artifact_path(
                    artifact_id
                )
            )

            db = sqlite3.connect(
                artifact_path
            )

            try:
                db.execute(
                    "PRAGMA foreign_keys=ON"
                )

                total = db.execute(
                    """
                    SELECT COUNT(*)
                    FROM chunks
                    """
                ).fetchone()[0]

                if total <= 0:
                    raise LocalComputeError(
                        LocalComputeErrorCode.PREPARATION_FAILED,
                        "Prepared artifact has no chunks to index.",
                    )

                self._initialize_index_tables(
                    db
                )

                self._update_job(
                    job_id,
                    "RUNNING",
                    "INDEXING",
                    10,
                    pipeline_job,
                )

                processed = 0
                last_chunk_index = -1

                batch_size = (
                    self.settings.indexing_batch_size
                )

                while processed < total:
                    self._cancel_if_requested(
                        job_id
                    )

                    rows = db.execute(
                        """
                        SELECT
                            id,
                            embedding_text,
                            content_text,
                            chunk_index
                        FROM chunks
                        WHERE chunk_index > ?
                        ORDER BY chunk_index ASC
                        LIMIT ?
                        """,
                        (
                            last_chunk_index,
                            batch_size,
                        ),
                    ).fetchall()

                    if not rows:
                        break

                    chunks_with_ids = [
                        (
                            row[0],
                            row[1],
                        )
                        for row in rows
                    ]

                    try:
                        vectors = (
                            embedder.encode_batch(
                                chunks_with_ids
                            )
                        )
                    except LocalComputeError:
                        raise
                    except Exception as exc:
                        raise LocalComputeError(
                            LocalComputeErrorCode.PREPARATION_FAILED,
                            "E5 embedding batch failed.",
                        ) from exc

                    if (
                        len(vectors)
                        != len(rows)
                    ):
                        raise LocalComputeError(
                            LocalComputeErrorCode.PREPARATION_FAILED,
                            "Embedding batch size mismatch.",
                        )

                    self._cancel_if_requested(
                        job_id
                    )

                    db.execute(
                        "BEGIN IMMEDIATE"
                    )

                    try:
                        fts_rows = []

                        for row, vector in zip(
                            rows,
                            vectors,
                        ):
                            chunk_id = row[0]
                            content_text = row[2]

                            normalized_vector = (
                                self._validated_vector(
                                    vector
                                )
                            )

                            db.execute(
                                """
                                INSERT INTO chunk_embeddings(
                                    chunk_id,
                                    model,
                                    dimension,
                                    normalized,
                                    index_version,
                                    vector
                                )
                                VALUES (?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    chunk_id,
                                    embedder.model_name,
                                    EMBEDDING_DIMENSION,
                                    1,
                                    INDEX_VERSION,
                                    normalized_vector.tobytes(
                                        order="C"
                                    ),
                                ),
                            )

                            fts_rows.append(
                                (
                                    chunk_id,
                                    content_text,
                                )
                            )

                        db.executemany(
                            """
                            INSERT INTO chunk_fts(
                                chunk_id,
                                content_text
                            )
                            VALUES (?, ?)
                            """,
                            fts_rows,
                        )

                        db.commit()

                    except Exception:
                        db.rollback()
                        raise

                    processed += len(rows)

                    last_chunk_index = int(
                        rows[-1][3]
                    )

                    local_progress = (
                        10
                        + int(
                            80
                            * processed
                            / total
                        )
                    )

                    self._update_job(
                        job_id,
                        "RUNNING",
                        "INDEXING",
                        local_progress,
                        pipeline_job,
                    )

                if processed != total:
                    raise LocalComputeError(
                        LocalComputeErrorCode.PREPARATION_FAILED,
                        "Not all prepared chunks were indexed.",
                    )

                self._cancel_if_requested(
                    job_id
                )

                self._update_job(
                    job_id,
                    "RUNNING",
                    "VALIDATING_INDEX",
                    94,
                    pipeline_job,
                )

                self._validate(
                    db,
                    total,
                    embedder.model_name,
                )

                db.execute(
                    "BEGIN IMMEDIATE"
                )

                try:
                    db.execute(
                        """
                        INSERT OR REPLACE
                        INTO artifact_metadata(
                            key,
                            value
                        )
                        VALUES(
                            'index_state',
                            'INDEX_READY'
                        )
                        """
                    )

                    db.commit()

                except Exception:
                    db.rollback()
                    raise

            finally:
                db.close()

            now = int(time.time())

            with self.catalog._connect() as connection:
                connection.execute(
                    """
                    UPDATE local_documents
                    SET preparation_state='INDEX_READY',
                        last_error_code=NULL,
                        updated_at=?
                    WHERE document_id=?
                    """,
                    (
                        now,
                        document_id,
                    ),
                )

            self.jobs.update(
                job_id,
                "SUCCEEDED",
                "INDEX_READY",
                100,
            )

            return {
                "job_id":
                    job_id,
                "document_id":
                    document_id,
                "artifact_id":
                    artifact_id,
                "index_state":
                    "INDEX_READY",
                "embedding_count":
                    total,
            }

        except LocalComputeError as exc:
            self._restore_not_indexed(
                artifact_id,
                document_id,
                exc.diagnostic_code or exc.code.value,
            )

            if (
                exc.code
                == LocalComputeErrorCode.JOB_CANCELLED
            ):
                self.jobs.update(
                    job_id,
                    "CANCELLED",
                    "CANCELLED",
                    100,
                    exc.diagnostic_code or exc.code.value,
                )
            else:
                self.jobs.update(
                    job_id,
                    "FAILED",
                    "FAILED",
                    100,
                    exc.diagnostic_code or exc.code.value,
                )

            raise

        except Exception as exc:
            error_code = (
                LocalComputeErrorCode.PREPARATION_FAILED.value
            )

            self._restore_not_indexed(
                artifact_id,
                document_id,
                error_code,
            )

            self.jobs.update(
                job_id,
                "FAILED",
                "FAILED",
                100,
                error_code,
            )

            raise LocalComputeError(
                LocalComputeErrorCode.PREPARATION_FAILED,
                "Local indexing failed.",
            ) from exc

    def _initialize_index_tables(
        self,
        db: sqlite3.Connection,
    ) -> None:
        """Start an idempotent index rebuild.

        If Compute is interrupted midway, a later retry clears the partial
        index and rebuilds it in bounded batches.
        """
        db.execute(
            "BEGIN IMMEDIATE"
        )

        try:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS chunk_embeddings(
                    chunk_id TEXT PRIMARY KEY
                        REFERENCES chunks(id),
                    model TEXT NOT NULL,
                    dimension INTEGER NOT NULL,
                    normalized INTEGER NOT NULL,
                    index_version TEXT NOT NULL,
                    vector BLOB NOT NULL
                        CHECK(length(vector)=3072)
                )
                """
            )

            db.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts
                USING fts5(
                    chunk_id UNINDEXED,
                    content_text
                )
                """
            )

            # A recovered/retried pipeline always starts from a clean partial
            # index. This is deterministic and avoids treating half an index as
            # queryable.
            db.execute(
                """
                DELETE FROM chunk_embeddings
                """
            )

            db.execute(
                """
                DELETE FROM chunk_fts
                """
            )

            db.execute(
                """
                INSERT OR REPLACE
                INTO artifact_metadata(
                    key,
                    value
                )
                VALUES(
                    'index_state',
                    'INDEXING'
                )
                """
            )

            db.commit()

        except Exception:
            db.rollback()
            raise

    def _update_job(
        self,
        job_id: str,
        state: str,
        stage: str,
        local_progress: int,
        pipeline_job: bool,
    ) -> None:
        local_progress = max(
            0,
            min(
                100,
                int(local_progress),
            ),
        )

        if pipeline_job:
            # Preparation completes at 60%. Indexing owns the remaining 40%.
            progress = (
                60
                + round(
                    local_progress
                    * 0.40
                )
            )

            progress = min(
                progress,
                99,
            )
        else:
            progress = local_progress

        self.jobs.update(
            job_id,
            state,
            stage,
            progress,
        )

    def _cancel_if_requested(
        self,
        job_id: str,
    ) -> None:
        if self.jobs.is_cancel_requested(
            job_id
        ):
            raise LocalComputeError(
                LocalComputeErrorCode.JOB_CANCELLED
            )

    @staticmethod
    def _validated_vector(
        vector,
    ) -> np.ndarray:
        value = np.asarray(
            vector,
            dtype=np.float32,
        )

        if (
            value.shape
            != (
                EMBEDDING_DIMENSION,
            )
            or not np.isfinite(
                value
            ).all()
            or not math.isclose(
                float(
                    np.linalg.norm(
                        value
                    )
                ),
                1.0,
                abs_tol=1e-4,
            )
        ):
            raise LocalComputeError(
                LocalComputeErrorCode.PREPARATION_FAILED,
                "Invalid canonical E5 embedding.",
            )

        return value

    def _validate(
        self,
        db: sqlite3.Connection,
        count: int,
        model: str,
    ) -> None:
        embedding_count = db.execute(
            """
            SELECT COUNT(*)
            FROM chunk_embeddings
            """
        ).fetchone()[0]

        lexical_count = db.execute(
            """
            SELECT COUNT(*)
            FROM chunk_fts
            """
        ).fetchone()[0]

        if (
            embedding_count != count
            or lexical_count != count
        ):
            raise LocalComputeError(
                LocalComputeErrorCode.PREPARATION_FAILED,
                "Index cardinality validation failed.",
            )

        cursor = db.execute(
            """
            SELECT
                dimension,
                normalized,
                model,
                index_version,
                vector
            FROM chunk_embeddings
            """
        )

        for (
            dimension,
            normalized,
            stored_model,
            index_version,
            blob,
        ) in cursor:
            vector = np.frombuffer(
                blob,
                dtype=np.float32,
            )

            if (
                dimension
                != EMBEDDING_DIMENSION
                or normalized != 1
                or stored_model != model
                or index_version
                != INDEX_VERSION
                or len(blob)
                != EMBEDDING_BYTES
                or vector.shape
                != (
                    EMBEDDING_DIMENSION,
                )
                or not np.isfinite(
                    vector
                ).all()
                or not math.isclose(
                    float(
                        np.linalg.norm(
                            vector
                        )
                    ),
                    1.0,
                    abs_tol=1e-4,
                )
            ):
                raise LocalComputeError(
                    LocalComputeErrorCode.PREPARATION_FAILED,
                    "Index embedding validation failed.",
                )

    def _restore_not_indexed(
        self,
        artifact_id: str,
        document_id: str,
        error_code: str,
    ) -> None:
        try:
            path = (
                self.settings.data_root
                / self._artifact_path(
                    artifact_id
                )
            )

            if path.exists():
                with sqlite3.connect(
                    path
                ) as db:
                    db.execute(
                        """
                        INSERT OR REPLACE
                        INTO artifact_metadata(
                            key,
                            value
                        )
                        VALUES(
                            'index_state',
                            'PREPARED_NOT_INDEXED'
                        )
                        """
                    )

                    db.commit()

        except Exception:
            # Best effort only. The catalog remains the authoritative
            # queryability gate.
            pass

        with self.catalog._connect() as connection:
            connection.execute(
                """
                UPDATE local_documents
                SET preparation_state='PREPARED_NOT_INDEXED',
                    last_error_code=?,
                    updated_at=?
                WHERE document_id=?
                """,
                (
                    error_code,
                    int(time.time()),
                    document_id,
                ),
            )

    def _document(
        self,
        document_id: str,
    ) -> dict:
        with self.catalog._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    document_id,
                    preparation_state,
                    active_artifact_id
                FROM local_documents
                WHERE document_id=?
                """,
                (
                    document_id,
                ),
            ).fetchone()

        if not row:
            raise LocalComputeError(
                LocalComputeErrorCode.DOCUMENT_NOT_FOUND
            )

        return dict(
            zip(
                (
                    "document_id",
                    "preparation_state",
                    "active_artifact_id",
                ),
                row,
            )
        )

    def _artifact_path(
        self,
        artifact_id: str,
    ) -> str:
        with self.catalog._connect() as connection:
            row = connection.execute(
                """
                SELECT relative_path
                FROM local_artifacts
                WHERE artifact_id=?
                """,
                (
                    artifact_id,
                ),
            ).fetchone()

        if not row:
            raise LocalComputeError(
                LocalComputeErrorCode.CAPABILITY_UNAVAILABLE,
                "Active local artifact is unavailable.",
            )

        return (
            row[0]
            + "/artifact.sqlite3"
        )
