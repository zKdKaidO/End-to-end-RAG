"""Small versioned SQLite catalog for local-control state only."""

from __future__ import annotations

import sqlite3
from pathlib import Path


CATALOG_SCHEMA_VERSION = 2


class LocalCatalog:
    def __init__(self, path: Path):
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)")
            current = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
            if current is None:
                self._apply_v1(connection)
                current = 1
            if current == 1:
                self._apply_v2(connection)
                current = 2
            if current != CATALOG_SCHEMA_VERSION:
                raise RuntimeError("LOCAL_CATALOG_SCHEMA_UNSUPPORTED")

    @staticmethod
    def _apply_v1(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE runtime_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE local_jobs (
                job_id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                operation TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
            """
        )
        connection.execute("INSERT INTO schema_migrations(version) VALUES (1)")

    @staticmethod
    def _apply_v2(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE local_documents (
                document_id TEXT PRIMARY KEY,
                content_sha256 TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                byte_size INTEGER NOT NULL,
                source_relative_path TEXT NOT NULL,
                preparation_state TEXT NOT NULL,
                active_artifact_id TEXT,
                last_error_code TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
            CREATE TABLE local_artifacts (
                artifact_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL REFERENCES local_documents(document_id),
                profile_id TEXT NOT NULL,
                profile_fingerprint TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                state TEXT NOT NULL,
                integrity_hash TEXT,
                page_count INTEGER NOT NULL DEFAULT 0,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                promoted_at INTEGER
            );
            ALTER TABLE local_jobs ADD COLUMN document_id TEXT;
            ALTER TABLE local_jobs ADD COLUMN artifact_id TEXT;
            ALTER TABLE local_jobs ADD COLUMN stage TEXT;
            ALTER TABLE local_jobs ADD COLUMN progress INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE local_jobs ADD COLUMN error_code TEXT;
            ALTER TABLE local_jobs ADD COLUMN cancellation_requested INTEGER NOT NULL DEFAULT 0;
            CREATE TABLE manifest_outbox (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                document_id TEXT NOT NULL,
                artifact_id TEXT,
                payload_metadata TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                acknowledged_at INTEGER
            );
            """
        )
        connection.execute("INSERT INTO schema_migrations(version) VALUES (2)")

    def set_metadata(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO runtime_metadata(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def get_metadata(self, key: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute("SELECT value FROM runtime_metadata WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys=ON")
        return connection
