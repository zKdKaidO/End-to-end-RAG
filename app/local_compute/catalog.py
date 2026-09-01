"""Small versioned SQLite catalog for local-control state only."""

from __future__ import annotations

import sqlite3
import json
from pathlib import Path


CATALOG_SCHEMA_VERSION = 3


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
            if current == 2:
                self._apply_v3(connection)
                current = 3
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

    @staticmethod
    def _apply_v3(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE paired_device_state (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                device_id TEXT NOT NULL,
                owner_user_id TEXT,
                credential_epoch INTEGER NOT NULL,
                platform_base_url TEXT NOT NULL,
                protocol_version TEXT NOT NULL,
                pairing_state TEXT NOT NULL,
                revocation_state TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            );
            CREATE TABLE control_manifest_outbox (
                document_id TEXT PRIMARY KEY,
                payload_metadata TEXT NOT NULL,
                revision INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                delivered_at INTEGER,
                terminal_error TEXT
            );
            """
        )
        connection.execute("INSERT INTO schema_migrations(version) VALUES (3)")

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

    def set_paired_device_state(self, state: dict) -> None:
        import time
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO paired_device_state(singleton,device_id,owner_user_id,credential_epoch,platform_base_url,protocol_version,pairing_state,revocation_state,updated_at) VALUES (1,?,?,?,?,?,?,?,?) ON CONFLICT(singleton) DO UPDATE SET device_id=excluded.device_id,owner_user_id=excluded.owner_user_id,credential_epoch=excluded.credential_epoch,platform_base_url=excluded.platform_base_url,protocol_version=excluded.protocol_version,pairing_state=excluded.pairing_state,revocation_state=excluded.revocation_state,updated_at=excluded.updated_at",
                (state["device_id"], state.get("owner_user_id"), state["credential_epoch"], state["platform_base_url"], state["protocol_version"], state.get("pairing_state", "PAIRED"), state.get("revocation_state", "ACTIVE"), int(time.time())),
            )

    def get_paired_device_state(self) -> dict | None:
        with self._connect() as connection:
            row=connection.execute("SELECT device_id,owner_user_id,credential_epoch,platform_base_url,protocol_version,pairing_state,revocation_state FROM paired_device_state WHERE singleton=1").fetchone()
        if not row: return None
        return dict(zip(("device_id","owner_user_id","credential_epoch","platform_base_url","protocol_version","pairing_state","revocation_state"), row))

    def enqueue_control_manifest(self, payload: dict, now: int) -> None:
        raw=json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self._connect() as connection:
            connection.execute("INSERT INTO control_manifest_outbox(document_id,payload_metadata,revision,created_at,updated_at,attempts,delivered_at,terminal_error) VALUES (?,?,1,?,?,0,NULL,NULL) ON CONFLICT(document_id) DO UPDATE SET payload_metadata=excluded.payload_metadata,revision=control_manifest_outbox.revision+1,updated_at=excluded.updated_at,delivered_at=NULL,terminal_error=NULL", (payload["document_id"],raw,now,now))

    def pending_control_manifests(self) -> list[dict]:
        with self._connect() as connection:
            rows=connection.execute("SELECT document_id,payload_metadata,revision,attempts FROM control_manifest_outbox WHERE delivered_at IS NULL AND terminal_error IS NULL ORDER BY updated_at,revision").fetchall()
        return [{"document_id":row[0],"payload":json.loads(row[1]),"revision":row[2],"attempts":row[3]} for row in rows]

    def mark_control_manifest_delivered(self, document_id: str, now: int) -> None:
        with self._connect() as connection:
            connection.execute("UPDATE control_manifest_outbox SET delivered_at=?, attempts=attempts+1 WHERE document_id=?",(now,document_id))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys=ON")
        return connection
