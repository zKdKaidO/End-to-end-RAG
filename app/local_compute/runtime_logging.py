"""Logging configuration owned by the windowed ZKD Compute runtime."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

import structlog


_CONFIGURATION_LOCK = threading.Lock()
_HANDLER_MARKER = "_zkd_local_compute_file_handler"


def configure_local_compute_logging(directory: Path) -> None:
    """Route structlog through a durable file handler, never standard streams.

    The desktop executable is built with PyInstaller ``console=False``. In
    that mode Windows exposes neither stdout nor stderr, so structlog's
    default PrintLoggerFactory is unsafe. Product audit events remain owned by
    ``LocalAuditLog``; this file is for regular structured application logs.
    """

    directory.mkdir(parents=True, exist_ok=True)
    with _CONFIGURATION_LOCK:
        root = logging.getLogger()

        # A stream handler built while stdout/stderr was absent is unsafe.
        # Preserve valid host/test handlers, but remove only the broken form.
        for handler in list(root.handlers):
            if getattr(handler, _HANDLER_MARKER, False) or (
                isinstance(handler, logging.StreamHandler)
                and getattr(handler, "stream", None) is None
            ):
                root.removeHandler(handler)
                handler.close()

        try:
            handler: logging.Handler = logging.FileHandler(
                directory / "application.jsonl",
                encoding="utf-8",
            )
        except OSError:
            # Logging must never make the local Compute control plane fail.
            # LocalAuditLog continues independently for required runtime
            # events, even if this supplementary application log is offline.
            handler = logging.NullHandler()

        setattr(handler, _HANDLER_MARKER, True)
        handler.setFormatter(logging.Formatter("%(message)s"))
        root.addHandler(handler)
        root.setLevel(logging.INFO)

        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
