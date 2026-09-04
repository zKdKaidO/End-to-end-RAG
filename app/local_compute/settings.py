"""Configuration for the standalone local Compute control service."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


PRODUCT_ORIGIN = "https://rag.zkd.id.vn"
PROTOCOL_VERSION = "zkd-compute-v1"
RUNTIME_VERSION = "0.1.0"


def default_data_root() -> Path:
    """Resolve the per-user Windows application-data root without a username."""
    local_app_data = os.environ.get("LOCALAPPDATA")

    if local_app_data:
        return Path(local_app_data) / "ZKD" / "Compute"

    return Path.home() / "AppData" / "Local" / "ZKD" / "Compute"


@dataclass(frozen=True)
class LocalComputeSettings:
    data_root: Path = field(default_factory=default_data_root)

    bind_host: str = "127.0.0.1"
    bind_port: int = 0

    production_origin: str = PRODUCT_ORIGIN
    development_mode: bool = False
    development_origins: tuple[str, ...] = ()

    protocol_version: str = PROTOCOL_VERSION
    runtime_version: str = RUNTIME_VERSION

    # Normal authenticated JSON/control requests stay intentionally small.
    request_body_max_bytes: int = 1 * 1024 * 1024

    # Product V1 PDF ceiling.
    #
    # We intentionally do not impose a page-count limit. Processing cost is
    # controlled by the durable pipeline and batched indexing instead.
    #
    # 250 MiB is large enough for real legal/reference PDFs while retaining a
    # safety boundary against accidental multi-gigabyte local uploads.
    source_pdf_max_bytes: int = 250 * 1024 * 1024

    session_lifetime_seconds: int = 300
    nonce_lifetime_seconds: int = 600

    max_concurrent_jobs: int = 1

    # Number of chunks embedded at once. This prevents a very large document
    # from requiring embeddings for every chunk to coexist in memory.
    indexing_batch_size: int = 32

    # Embedded durable worker idle cadence.
    pipeline_poll_seconds: float = 0.25

    endpoint_generation: str | None = None

    local_generation_base_url: str = "http://127.0.0.1:11434"
    platform_base_url: str = PRODUCT_ORIGIN

    control_heartbeat_seconds: int = 30
    control_backoff_min_seconds: float = 1.0
    control_backoff_max_seconds: float = 60.0
    control_auto_start: bool = True

    platform_grant_verification_public_key: str = ""

    def __post_init__(self) -> None:
        if self.bind_host != "127.0.0.1":
            raise ValueError("LOCAL_COMPUTE_LOOPBACK_ONLY")

        if not 0 <= self.bind_port <= 65535:
            raise ValueError("LOCAL_COMPUTE_INVALID_PORT")

        if (
            self.request_body_max_bytes <= 0
            or self.source_pdf_max_bytes <= 0
            or self.session_lifetime_seconds <= 0
        ):
            raise ValueError("LOCAL_COMPUTE_INVALID_LIMIT")

        if (
            self.nonce_lifetime_seconds <= 0
            or self.max_concurrent_jobs <= 0
            or self.indexing_batch_size <= 0
            or self.pipeline_poll_seconds <= 0
        ):
            raise ValueError("LOCAL_COMPUTE_INVALID_LIMIT")

        if not self.production_origin.startswith("https://"):
            raise ValueError("LOCAL_COMPUTE_INVALID_PRODUCTION_ORIGIN")

        if (
            not self.development_mode
            and not self.platform_base_url.startswith("https://")
        ):
            raise ValueError("LOCAL_COMPUTE_PLATFORM_HTTPS_REQUIRED")

        if (
            self.control_heartbeat_seconds <= 0
            or self.control_backoff_min_seconds <= 0
            or self.control_backoff_max_seconds < self.control_backoff_min_seconds
        ):
            raise ValueError("LOCAL_COMPUTE_INVALID_CONTROL_CADENCE")

        if not self.development_mode and self.development_origins:
            raise ValueError(
                "LOCAL_COMPUTE_DEVELOPMENT_ORIGINS_REQUIRE_DEVELOPMENT_MODE"
            )

    @property
    def allowed_origins(self) -> tuple[str, ...]:
        if self.development_mode:
            return (
                self.production_origin,
                *self.development_origins,
            )

        return (self.production_origin,)

    @property
    def catalog_path(self) -> Path:
        return self.data_root / "state" / "catalog.sqlite3"

    @property
    def logs_path(self) -> Path:
        return self.data_root / "logs"

    @property
    def tmp_path(self) -> Path:
        return self.data_root / "tmp"

    @property
    def documents_path(self) -> Path:
        return self.data_root / "documents"

    @property
    def artifacts_path(self) -> Path:
        return self.data_root / "artifacts"