"""Local-only Block 1/2 preparation wrapper; intentionally excludes embeddings."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import time
import uuid

from app.pdf.extractor import PDFExtractor
from app.processing.cleaner import PageCleaner
from app.processing.header_footer import HeaderFooterRemover
from app.processing.reconstruction import DocumentReconstructor
from app.processing.metadata_extractor import MetadataExtractor
from app.processing.parser import LegalParser
from app.processing.chunker import Chunker
from app.indexing.artifact import (
    CanonicalEmbeddingArtifactError,
    validate_canonical_e5_artifact,
)
from app.indexing.input_contract import get_e5_input_contract

from .documents import LocalDocumentStore
from .errors import LocalComputeError, LocalComputeErrorCode
from .jobs import LocalJobStore
from .settings import LocalComputeSettings


ARTIFACT_SCHEMA_VERSION = 1
ARTIFACT_PROFILE_ID = "zkd-local-artifact-v1"

PERSIST_BATCH_SIZE = 256


def artifact_fingerprint() -> str:
    payload = {
        "schema": 1,
        "parser": "block2-v1",
        "chunking": "block2-token-safe-v1",
        "embedding_model": "intfloat/multilingual-e5-base",
        "dimension": 768,
        "normalized": True,
        "passage_prefix": "passage: ",
        "query_prefix": "query: ",
        "token_limit": 512,
        "index_version": "block3-v1",
        "retrieval_store": "sqlite-v1",
        "hierarchy": "legal-units-v1",
    }

    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


class LocalPreparationService:
    def __init__(
        self,
        settings: LocalComputeSettings,
        catalog,
    ):
        self.settings = settings
        self.catalog = catalog
        self.documents = LocalDocumentStore(
            settings,
            catalog,
        )
        self.jobs = LocalJobStore(catalog)

    def prepare(
        self,
        document_id: str,
        job_id: str | None = None,
    ) -> dict:
        """Prepare a local document.

        When job_id is omitted this preserves the old synchronous API contract
        and creates a dedicated PREPARE_DOCUMENT job.

        When job_id is supplied the caller owns a durable PROCESS_DOCUMENT job.
        Preparation updates that same job instead of creating nested jobs.
        """
        with self.catalog.document_lock(document_id):
            return self._prepare_locked(
                document_id,
                job_id=job_id,
            )

    def _prepare_locked(
        self,
        document_id: str,
        job_id: str | None = None,
    ) -> dict:
        document = self.documents.get(document_id)

        if not document:
            raise LocalComputeError(
                LocalComputeErrorCode.DOCUMENT_NOT_FOUND
            )

        pipeline_job = job_id is not None

        if pipeline_job:
            job = self.jobs.get(job_id)

            if (
                not job
                or job.get("document_id") != document_id
            ):
                raise LocalComputeError(
                    LocalComputeErrorCode.INVALID_REQUEST,
                    "Preparation job does not belong to the document.",
                )
        else:
            job_id = None

        self._cleanup_stale_staging(document_id)

        artifact_id = str(uuid.uuid4())

        if job_id is None:
            job_id = self.jobs.enqueue_preparation(
                document_id,
                artifact_id,
            )
        else:
            self.jobs.attach_artifact(
                job_id,
                artifact_id,
            )

        staging = (
            self.settings.artifacts_path
            / document_id
            / f"{artifact_id}.staging"
        )

        final = (
            self.settings.artifacts_path
            / document_id
            / artifact_id
        )

        try:
            self._update_doc(
                document_id,
                "PROCESSING",
            )

            self._update_job(
                job_id,
                "RUNNING",
                "EXTRACTING",
                5,
                pipeline_job,
            )

            staging.mkdir(
                parents=True,
                exist_ok=False,
            )

            self._cancel_if_requested(job_id)

            source_path = self.documents.source_path(
                document_id
            )

            source_bytes = source_path.read_bytes()

            try:
                pages = list(
                    PDFExtractor.extract_pages(
                        source_bytes,
                        max_pages=None,
                        max_page_extracted_chars=(
                            self.settings.source_pdf_max_page_extracted_chars
                        ),
                        max_extracted_chars=(
                            self.settings.source_pdf_max_extracted_chars
                        ),
                    )
                )
            finally:
                # Do not retain an unnecessary second full PDF allocation while
                # text processing continues.
                del source_bytes

            if not pages:
                raise LocalComputeError(
                    LocalComputeErrorCode.PREPARATION_FAILED,
                    "No PDF pages were extracted.",
                )

            self._update_job(
                job_id,
                "RUNNING",
                "CLEANING",
                20,
                pipeline_job,
            )

            self._cancel_if_requested(job_id)

            cleaner = PageCleaner()

            cleaned = HeaderFooterRemover().remove_headers_footers(
                [
                    cleaner.clean(page["raw_text"])
                    for page in pages
                ]
            )

            self._update_job(
                job_id,
                "RUNNING",
                "RECONSTRUCTING",
                30,
                pipeline_job,
            )

            normalized, offsets = (
                DocumentReconstructor().reconstruct(
                    cleaned
                )
            )

            # Release the additional cleaned-page representation once the
            # canonical normalized text exists.
            del cleaned

            if not normalized.strip():
                raise LocalComputeError(
                    LocalComputeErrorCode.UNSUPPORTED_TEXTLESS_PDF,
                    "Text-native PDF content is required.",
                )

            self._cancel_if_requested(job_id)

            self._update_doc(
                document_id,
                "CHUNKING",
            )

            self._update_job(
                job_id,
                "RUNNING",
                "PARSING",
                38,
                pipeline_job,
            )

            metadata = MetadataExtractor().extract(
                normalized
            )

            units = LegalParser().parse(
                normalized
            )

            self._cancel_if_requested(job_id)

            self._update_job(
                job_id,
                "RUNNING",
                "CHUNKING",
                48,
                pipeline_job,
            )

            try:
                validate_canonical_e5_artifact(
                    str(self.settings.embedding_model_cache_dir)
                )
                chunker = Chunker(
                    input_contract=get_e5_input_contract(
                        str(self.settings.embedding_model_cache_dir)
                    )
                )
                chunks = chunker.generate_chunks(
                    normalized,
                    units,
                    metadata,
                )
            except (CanonicalEmbeddingArtifactError, OSError, ValueError) as exc:
                raise LocalComputeError(
                    LocalComputeErrorCode.MODEL_ARTIFACT_UNAVAILABLE,
                    "Canonical E5 tokenizer artifact is unavailable.",
                    diagnostic_code=self._tokenizer_diagnostic_code(exc),
                ) from exc

            if not chunks:
                raise LocalComputeError(
                    LocalComputeErrorCode.PREPARATION_FAILED,
                    "No valid chunks were created.",
                )

            self._enrich(
                chunks,
                metadata,
                document_id,
                offsets,
            )

            self._map_units(
                units,
                offsets,
            )

            self._cancel_if_requested(job_id)

            self._update_doc(
                document_id,
                "VALIDATING",
            )

            self._update_job(
                job_id,
                "RUNNING",
                "PERSISTING",
                70,
                pipeline_job,
            )

            artifact_db = (
                staging
                / "artifact.sqlite3"
            )

            self._persist(
                artifact_db,
                document,
                artifact_id,
                pages,
                normalized,
                offsets,
                units,
                chunks,
                metadata,
                chunker,
                job_id,
                pipeline_job,
            )

            self._cancel_if_requested(job_id)

            self._update_job(
                job_id,
                "RUNNING",
                "VALIDATING",
                92,
                pipeline_job,
            )

            self._validate(
                artifact_db,
                document,
                artifact_id,
            )

            self._cancel_if_requested(job_id)

            os.replace(
                staging,
                final,
            )

            integrity = self._hash_file(
                final
                / "artifact.sqlite3"
            )

            now = int(time.time())

            with self.catalog._connect() as db:
                db.execute(
                    """
                    INSERT INTO local_artifacts(
                        artifact_id,
                        document_id,
                        profile_id,
                        profile_fingerprint,
                        relative_path,
                        state,
                        integrity_hash,
                        page_count,
                        chunk_count,
                        created_at,
                        promoted_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact_id,
                        document_id,
                        ARTIFACT_PROFILE_ID,
                        artifact_fingerprint(),
                        str(
                            final.relative_to(
                                self.settings.data_root
                            )
                        ),
                        "PREPARED_NOT_INDEXED",
                        integrity,
                        len(pages),
                        len(chunks),
                        now,
                        now,
                    ),
                )

                db.execute(
                    """
                    UPDATE local_documents
                    SET active_artifact_id=?,
                        preparation_state='PREPARED_NOT_INDEXED',
                        last_error_code=NULL,
                        updated_at=?
                    WHERE document_id=?
                    """,
                    (
                        artifact_id,
                        now,
                        document_id,
                    ),
                )

            if pipeline_job:
                self.jobs.update(
                    job_id,
                    "RUNNING",
                    "PREPARED_NOT_INDEXED",
                    60,
                )
            else:
                self.jobs.update(
                    job_id,
                    "SUCCEEDED",
                    "PREPARED_NOT_INDEXED",
                    100,
                )

            return {
                "job_id": job_id,
                "document_id": document_id,
                "artifact_id": artifact_id,
                "preparation_state": "PREPARED_NOT_INDEXED",
                "page_count": len(pages),
                "chunk_count": len(chunks),
            }

        except LocalComputeError as exc:
            self._remove_staging(staging)

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

            if not document.get(
                "active_artifact_id"
            ):
                self._update_doc(
                    document_id,
                    "FAILED",
                    exc.diagnostic_code or exc.code.value,
                )

            raise

        except Exception as exc:
            self._remove_staging(staging)

            self.jobs.update(
                job_id,
                "FAILED",
                "FAILED",
                100,
                LocalComputeErrorCode.PREPARATION_FAILED.value,
            )

            if not document.get(
                "active_artifact_id"
            ):
                self._update_doc(
                    document_id,
                    "FAILED",
                    LocalComputeErrorCode.PREPARATION_FAILED.value,
                )

            raise LocalComputeError(
                LocalComputeErrorCode.PREPARATION_FAILED,
                "Local preparation failed.",
            ) from exc

    def _update_job(
        self,
        job_id: str,
        state: str,
        stage: str,
        local_progress: int,
        pipeline_job: bool,
    ) -> None:
        if pipeline_job:
            # Preparation owns 0..60 of a combined prepare/index pipeline.
            progress = round(
                max(
                    0,
                    min(
                        100,
                        local_progress,
                    ),
                )
                * 0.60
            )
        else:
            progress = max(
                0,
                min(
                    100,
                    local_progress,
                ),
            )

        self.jobs.update(
            job_id,
            state,
            stage,
            progress,
        )

    @staticmethod
    def _tokenizer_diagnostic_code(error: BaseException) -> str:
        if isinstance(error, CanonicalEmbeddingArtifactError):
            # Artifact validation only emits a fixed allow-list of suffixes;
            # do not persist arbitrary exception text or local paths.
            return str(error).rsplit(":", 1)[-1]
        return "tokenizer_load_failed"

    def _update_doc(
        self,
        document_id: str,
        state: str,
        error: str | None = None,
    ) -> None:
        with self.catalog._connect() as db:
            db.execute(
                """
                UPDATE local_documents
                SET preparation_state=?,
                    last_error_code=?,
                    updated_at=?
                WHERE document_id=?
                """,
                (
                    state,
                    error,
                    int(time.time()),
                    document_id,
                ),
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
    def _page(
        offset: int,
        offsets,
    ):
        for item in offsets:
            if (
                item["char_start"]
                <= offset
                <= item["char_end"]
            ):
                return item[
                    "page_number"
                ]

        return (
            offsets[-1]["page_number"]
            if offsets
            else -1
        )

    def _enrich(
        self,
        chunks,
        metadata,
        document_id: str,
        offsets,
    ) -> None:
        for chunk in chunks:
            chunk[
                "metadata_json"
            ] = metadata

            chunk[
                "page_start"
            ] = self._page(
                chunk["char_start"],
                offsets,
            )

            chunk[
                "page_end"
            ] = self._page(
                max(
                    chunk["char_start"],
                    chunk["char_end"] - 1,
                ),
                offsets,
            )

            chunk[
                "provenance_json"
            ] = {
                "document_id":
                    document_id,
                "page_start":
                    chunk["page_start"],
                "page_end":
                    chunk["page_end"],
                "char_start":
                    chunk["char_start"],
                "char_end":
                    chunk["char_end"],
                **(
                    {
                        "split":
                            chunk["split"]
                    }
                    if "split" in chunk
                    else {}
                ),
            }

    def _map_units(
        self,
        units,
        offsets,
    ) -> None:
        for unit in units:
            unit.local_id = str(
                uuid.uuid4()
            )

            unit.page_start = self._page(
                unit.start_char,
                offsets,
            )

            unit.page_end = self._page(
                unit.end_char,
                offsets,
            )

            self._map_units(
                unit.children,
                offsets,
            )

    def _persist(
        self,
        path,
        document,
        artifact_id: str,
        pages,
        text: str,
        offsets,
        units,
        chunks,
        metadata,
        chunker: Chunker,
        job_id: str,
        pipeline_job: bool,
    ) -> None:
        db = sqlite3.connect(path)

        try:
            db.execute(
                "PRAGMA foreign_keys=ON"
            )

            db.executescript(
                """
                CREATE TABLE schema_migrations(
                    version INTEGER PRIMARY KEY
                );

                INSERT INTO schema_migrations
                VALUES(1);

                CREATE TABLE artifact_metadata(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE pages(
                    page_number INTEGER PRIMARY KEY,
                    raw_text TEXT NOT NULL,
                    char_count INTEGER NOT NULL
                );

                CREATE TABLE reconstruction(
                    id INTEGER PRIMARY KEY CHECK(id=1),
                    normalized_text TEXT NOT NULL,
                    page_offset_map TEXT NOT NULL
                );

                CREATE TABLE legal_units(
                    id TEXT PRIMARY KEY,
                    parent_id TEXT REFERENCES legal_units(id),
                    unit_type TEXT,
                    unit_number TEXT,
                    unit_title TEXT,
                    char_start INTEGER,
                    char_end INTEGER,
                    page_start INTEGER,
                    page_end INTEGER,
                    level INTEGER
                );

                CREATE TABLE chunks(
                    id TEXT PRIMARY KEY,
                    document_id TEXT,
                    legal_unit_id TEXT REFERENCES legal_units(id),
                    chunk_index INTEGER UNIQUE,
                    content_text TEXT,
                    embedding_text TEXT,
                    token_count INTEGER,
                    page_start INTEGER,
                    page_end INTEGER,
                    metadata_json TEXT,
                    provenance_json TEXT
                );
                """
            )

            artifact_metadata = {
                "artifact_id":
                    artifact_id,
                "profile_id":
                    ARTIFACT_PROFILE_ID,
                "profile_fingerprint":
                    artifact_fingerprint(),
                "source_sha256":
                    document[
                        "content_sha256"
                    ],
                "document_id":
                    document[
                        "document_id"
                    ],
                "state":
                    "PREPARED_NOT_INDEXED",
                "metadata":
                    json.dumps(
                        metadata,
                        ensure_ascii=False,
                    ),
            }

            db.executemany(
                """
                INSERT INTO artifact_metadata
                VALUES (?, ?)
                """,
                artifact_metadata.items(),
            )

            db.executemany(
                """
                INSERT INTO pages
                VALUES (?, ?, ?)
                """,
                (
                    (
                        page["page_number"],
                        page["raw_text"],
                        page["char_count"],
                    )
                    for page in pages
                ),
            )

            db.execute(
                """
                INSERT INTO reconstruction
                VALUES(1, ?, ?)
                """,
                (
                    text,
                    json.dumps(
                        offsets,
                        ensure_ascii=False,
                    ),
                ),
            )

            def put_unit(
                unit,
                parent_id=None,
            ) -> None:
                db.execute(
                    """
                    INSERT INTO legal_units
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        unit.local_id,
                        parent_id,
                        unit.unit_type,
                        unit.unit_number,
                        unit.title,
                        unit.start_char,
                        unit.end_char,
                        unit.page_start,
                        unit.page_end,
                        unit.level,
                    ),
                )

                for child in (
                    unit.children
                ):
                    put_unit(
                        child,
                        unit.local_id,
                    )

            for unit in units:
                put_unit(unit)

            token_contract = (
                chunker.input_contract
            )

            total_chunks = len(chunks)

            for start in range(
                0,
                total_chunks,
                PERSIST_BATCH_SIZE,
            ):
                self._cancel_if_requested(
                    job_id
                )

                batch = chunks[
                    start:
                    start
                    + PERSIST_BATCH_SIZE
                ]

                rows = []

                for chunk in batch:
                    rows.append(
                        (
                            str(
                                uuid.uuid4()
                            ),
                            document[
                                "document_id"
                            ],
                            chunk[
                                "legal_unit"
                            ].local_id,
                            chunk[
                                "chunk_index"
                            ],
                            chunk[
                                "content_text"
                            ],
                            chunk[
                                "embedding_text"
                            ],
                            token_contract.count_final_tokens(
                                chunk[
                                    "embedding_text"
                                ]
                            ),
                            chunk[
                                "page_start"
                            ],
                            chunk[
                                "page_end"
                            ],
                            json.dumps(
                                chunk[
                                    "metadata_json"
                                ],
                                ensure_ascii=False,
                            ),
                            json.dumps(
                                chunk[
                                    "provenance_json"
                                ],
                                ensure_ascii=False,
                            ),
                        )
                    )

                db.executemany(
                    """
                    INSERT INTO chunks
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )

                completed = min(
                    start + len(batch),
                    total_chunks,
                )

                if total_chunks:
                    local_progress = (
                        70
                        + int(
                            18
                            * completed
                            / total_chunks
                        )
                    )

                    self._update_job(
                        job_id,
                        "RUNNING",
                        "PERSISTING",
                        local_progress,
                        pipeline_job,
                    )

            db.commit()

        finally:
            db.close()

    def _validate(
        self,
        path,
        document,
        artifact_id: str,
    ) -> None:
        db = sqlite3.connect(path)

        try:
            schema = db.execute(
                """
                SELECT MAX(version)
                FROM schema_migrations
                """
            ).fetchone()[0]

            chunk_counts = db.execute(
                """
                SELECT
                    COUNT(*),
                    COUNT(DISTINCT chunk_index)
                FROM chunks
                """
            ).fetchone()

            profile = dict(
                db.execute(
                    """
                    SELECT key, value
                    FROM artifact_metadata
                    """
                ).fetchall()
            )

            if (
                schema
                != ARTIFACT_SCHEMA_VERSION
                or chunk_counts[0] == 0
                or chunk_counts[0]
                != chunk_counts[1]
                or profile.get(
                    "source_sha256"
                )
                != document[
                    "content_sha256"
                ]
                or profile.get(
                    "profile_fingerprint"
                )
                != artifact_fingerprint()
                or profile.get(
                    "artifact_id"
                )
                != artifact_id
            ):
                raise LocalComputeError(
                    LocalComputeErrorCode.PREPARATION_FAILED,
                    "Artifact validation failed.",
                )

        finally:
            db.close()

    def _cleanup_stale_staging(
        self,
        document_id: str,
    ) -> None:
        root = (
            self.settings.artifacts_path
            / document_id
        )

        if not root.exists():
            return

        for child in root.iterdir():
            if (
                child.is_dir()
                and child.name.endswith(
                    ".staging"
                )
            ):
                shutil.rmtree(
                    child,
                    ignore_errors=True,
                )

    @staticmethod
    def _remove_staging(
        staging,
    ) -> None:
        if staging.exists():
            shutil.rmtree(
                staging,
                ignore_errors=True,
            )

    @staticmethod
    def _hash_file(path) -> str:
        digest = hashlib.sha256()

        with path.open("rb") as handle:
            for block in iter(
                lambda: handle.read(
                    1024 * 1024
                ),
                b"",
            ):
                digest.update(block)

        return digest.hexdigest()
