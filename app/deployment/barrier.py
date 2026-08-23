from __future__ import annotations

import time
from contextlib import contextmanager

import psycopg2

from app.core.config import settings
from app.deployment.constants import BACKUP_BARRIER_KEY


class BackupBarrierTimeout(RuntimeError):
    pass


@contextmanager
def cross_store_barrier(*, exclusive: bool, timeout_seconds: float = 120.0):
    """Hold a session advisory lock across a complete cross-store operation."""
    connection = psycopg2.connect(settings.DATABASE_URL)
    connection.autocommit = True
    function = "pg_try_advisory_lock" if exclusive else "pg_try_advisory_lock_shared"
    unlock = "pg_advisory_unlock" if exclusive else "pg_advisory_unlock_shared"
    deadline = time.monotonic() + timeout_seconds
    acquired = False
    try:
        with connection.cursor() as cursor:
            while time.monotonic() < deadline:
                cursor.execute(f"SELECT {function}(%s)", (BACKUP_BARRIER_KEY,))
                if cursor.fetchone()[0]:
                    acquired = True
                    break
                time.sleep(0.1)
        if not acquired:
            raise BackupBarrierTimeout("BACKUP_BARRIER_TIMEOUT")
        yield
    finally:
        if acquired:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"SELECT {unlock}(%s)", (BACKUP_BARRIER_KEY,))
            finally:
                connection.close()
        else:
            connection.close()
