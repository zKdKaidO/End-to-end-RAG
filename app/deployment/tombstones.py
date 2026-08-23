from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.core.config import settings
from app.deployment.constants import TOMBSTONE_FORMAT_VERSION


class TombstoneStoreUnavailable(RuntimeError):
    pass


_thread_lock = threading.Lock()


@dataclass(frozen=True)
class DeletionTombstone:
    tombstone_format_version: int
    subject_user_id: str
    account_deletion_job_id: str
    deletion_requested_at: str


@contextmanager
def _locked_file(path: Path, mode: str) -> Iterator[object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _thread_lock, path.open(mode, encoding="utf-8") as handle:
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield handle
        finally:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class DeletionTombstoneStore:
    def __init__(self, control_dir: str | Path | None = None):
        self.control_dir = Path(control_dir or settings.RECOVERY_CONTROL_DIR).resolve()
        self.path = self.control_dir / "deletion-tombstones.jsonl"

    def record(self, subject_user_id: str, account_deletion_job_id: str, requested_at: datetime) -> DeletionTombstone:
        item = DeletionTombstone(
            tombstone_format_version=TOMBSTONE_FORMAT_VERSION,
            subject_user_id=str(subject_user_id),
            account_deletion_job_id=str(account_deletion_job_id),
            deletion_requested_at=requested_at.astimezone(timezone.utc).isoformat(),
        )
        try:
            with _locked_file(self.path, "a+") as handle:
                handle.seek(0)
                existing = [json.loads(line) for line in handle if line.strip()]
                if not any(row.get("account_deletion_job_id") == item.account_deletion_job_id for row in existing):
                    handle.seek(0, os.SEEK_END)
                    handle.write(json.dumps(asdict(item), sort_keys=True, separators=(",", ":")) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
            return item
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise TombstoneStoreUnavailable("DELETION_TOMBSTONE_WRITE_FAILED") from exc

    def contains(self, account_deletion_job_id: str) -> bool:
        return any(item.account_deletion_job_id == str(account_deletion_job_id) for item in self.read_all())

    def read_all(self) -> list[DeletionTombstone]:
        if not self.path.exists():
            return []
        try:
            with _locked_file(self.path, "r+") as handle:
                handle.seek(0)
                rows = [json.loads(line) for line in handle if line.strip()]
            return [DeletionTombstone(**row) for row in rows]
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise TombstoneStoreUnavailable("DELETION_TOMBSTONE_READ_FAILED") from exc

    def newer_than(self, snapshot_at: datetime) -> list[DeletionTombstone]:
        snapshot = snapshot_at.astimezone(timezone.utc)
        return [
            item for item in self.read_all()
            if datetime.fromisoformat(item.deletion_requested_at).astimezone(timezone.utc) > snapshot
        ]

    def assert_available(self) -> None:
        self.control_dir.mkdir(parents=True, exist_ok=True)
        probe = self.control_dir / ".tombstone-probe"
        try:
            probe.write_text("ok", encoding="utf-8")
            with probe.open("rb") as handle:
                os.fsync(handle.fileno())
            probe.unlink()
        except OSError as exc:
            raise TombstoneStoreUnavailable("DELETION_TOMBSTONE_STORE_UNAVAILABLE") from exc


deletion_tombstone_store = DeletionTombstoneStore()
