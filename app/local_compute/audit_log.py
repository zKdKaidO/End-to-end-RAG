"""Privacy-safe JSONL audit logging for the local control boundary."""

from __future__ import annotations

import json
import time
from pathlib import Path


class LocalAuditLog:
    def __init__(self, directory: Path):
        self.path = directory / "runtime.jsonl"

    def record(self, request_id: str, operation: str, duration_ms: int, status_code: int) -> None:
        event = {
            "timestamp": int(time.time()),
            "request_id": request_id,
            "operation": operation,
            "duration_ms": duration_ms,
            "status_code": status_code,
        }
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, separators=(",", ":")) + "\n")
