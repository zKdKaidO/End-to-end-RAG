"""Small versioned SQLite catalog for local-control state only."""

from __future__ import annotations

import sqlite3
from pathlib import Path


CATALOG_SCHEMA_VERSION = 1


class LocalCatalog:
    def __init__(self, path: Path):
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)")
            current = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
            if current is None:
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
                connection.execute("INSERT INTO schema_migrations(version) VALUES (?)", (CATALOG_SCHEMA_VERSION,))
            elif current != CATALOG_SCHEMA_VERSION:
                raise RuntimeError("LOCAL_CATALOG_SCHEMA_UNSUPPORTED")

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
