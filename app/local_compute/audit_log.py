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
        self._write(event)

    def record_control_event(
        self,
        event_name: str,
        *,
        state: str,
        delay_seconds: float | None = None,
        exception_class: str | None = None,
    ) -> None:
        """Record control-channel liveness without remote or secret data."""
        event = {
            "timestamp": int(time.time()),
            "event": event_name,
            "state": state,
        }
        if delay_seconds is not None:
            event["delay_seconds"] = round(delay_seconds, 3)
        if exception_class is not None:
            event["exception_class"] = exception_class
        self._write(event)

    def record_cors_preflight(
        self,
        *,
        path: str,
        origin: str,
        requested_method: str,
        requested_headers: list[str],
        private_network_requested: bool,
        response_headers: dict[str, str],
        status_code: int,
    ) -> None:
        """Record only the fixed CORS/PNA preflight metadata needed for transport diagnosis.

        Request values, credentials, and content are intentionally impossible to pass here.
        ``requested_headers`` contains normalized HTTP header *names* only.
        """
        self._write(
            {
                "timestamp": int(time.time()),
                "event": "cors_preflight",
                "path": path,
                "origin": origin,
                "requested_method": requested_method,
                "requested_headers": requested_headers,
                "private_network_requested": private_network_requested,
                "response_allow_origin": response_headers.get(
                    "Access-Control-Allow-Origin"
                ),
                "response_allow_methods": response_headers.get(
                    "Access-Control-Allow-Methods"
                ),
                "response_allow_headers": response_headers.get(
                    "Access-Control-Allow-Headers"
                ),
                "response_allow_private_network": response_headers.get(
                    "Access-Control-Allow-Private-Network"
                ),
                "status_code": status_code,
            }
        )

    def record_answer_transport_stage(
        self,
        event_name: str,
        **fields: object,
    ) -> None:
        """Record fixed-schema, content-free diagnostics for ``POST /v1/answers``.

        Callers may supply only fixed route metadata, HTTP header names, numeric
        lengths, and LocalComputeError enum names. Never pass values from a
        request header or request body.
        """
        event = {
            "timestamp": int(time.time()),
            "event": event_name,
            **fields,
        }
        self._write(event)

    def _write(self, event: dict) -> None:
        # The schema intentionally contains no request body, request-header
        # values, text, prompts, model output, or local filesystem paths.
        encoded = json.dumps(event, separators=(",", ":")) + "\n"
        with self._lock:
            self._rotate_if_needed()
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(encoded)
