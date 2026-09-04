"""Privacy-safe JSONL audit logging for the local control boundary."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path


class LocalAuditLog:
    def __init__(self, directory: Path, max_bytes: int = 5 * 1024 * 1024, backup_count: int = 5):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "runtime.jsonl"
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._lock = threading.Lock()

    def _rotate_if_needed(self) -> None:
        if not self.path.exists() or self.path.stat().st_size < self.max_bytes:
            return
        oldest = self.path.with_name(f"{self.path.name}.{self.backup_count}")
        oldest.unlink(missing_ok=True)
        for number in range(self.backup_count - 1, 0, -1):
            current = self.path.with_name(f"{self.path.name}.{number}")
            if current.exists():
                os.replace(current, self.path.with_name(f"{self.path.name}.{number + 1}"))
        os.replace(self.path, self.path.with_name(f"{self.path.name}.1"))

    def record(self, request_id: str, operation: str, duration_ms: int, status_code: int) -> None:
        event = {
            "timestamp": int(time.time()),
            "request_id": request_id,
            "operation": operation,
            "duration_ms": duration_ms,
            "status_code": status_code,
        }
        # The schema intentionally contains no request body, headers, text,
        # prompts, model output, or local filesystem paths.
        encoded = json.dumps(event, separators=(",", ":")) + "\n"
        with self._lock:
            self._rotate_if_needed()
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(encoded)
