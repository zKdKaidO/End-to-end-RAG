"""Lifecycle, endpoint identity, capabilities, and local state foundation."""

from __future__ import annotations

import socket
import uuid
from enum import Enum

from .audit_log import LocalAuditLog
from .catalog import LocalCatalog
from .sessions import DevelopmentGrantVerifier, LocalSessionManager, UnavailableGrantVerifier
from .settings import LocalComputeSettings


class RuntimeState(str, Enum):
    OFFLINE = "OFFLINE"
    CONNECTING = "CONNECTING"
    AUTHENTICATING = "AUTHENTICATING"
    READY = "READY"
    BUSY = "BUSY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    REVOKED = "REVOKED"
    UPDATE_REQUIRED = "UPDATE_REQUIRED"


CAPABILITY_NAMES = ("pdf_processing", "chunking", "embedding", "indexing", "retrieval", "generation")


class LocalComputeRuntime:
    def __init__(self, settings: LocalComputeSettings):
        self.settings = settings
        self.catalog = LocalCatalog(settings.catalog_path)
        self.sessions = LocalSessionManager(settings.session_lifetime_seconds, settings.nonce_lifetime_seconds)
        self.grant_verifier = DevelopmentGrantVerifier() if settings.development_mode else UnavailableGrantVerifier()
        self.state = RuntimeState.OFFLINE
        self.endpoint_generation = settings.endpoint_generation or str(uuid.uuid4())
        self.bound_port: int | None = None
        self.audit_log: LocalAuditLog | None = None
        self._generation_capability = "NOT_READY"
        self._generation_router = None

    def start(self) -> None:
        self.settings.data_root.mkdir(parents=True, exist_ok=True)
        self.settings.logs_path.mkdir(parents=True, exist_ok=True)
        self.settings.tmp_path.mkdir(parents=True, exist_ok=True)
        self.settings.documents_path.mkdir(parents=True, exist_ok=True)
        self.settings.artifacts_path.mkdir(parents=True, exist_ok=True)
        self.catalog.initialize()
        self.audit_log = LocalAuditLog(self.settings.logs_path)
        self.catalog.set_metadata("protocol_version", self.settings.protocol_version)
        self.catalog.set_metadata("endpoint_generation", self.endpoint_generation)
        from .jobs import LocalJobStore
        LocalJobStore(self.catalog).reconcile_interrupted()
        self.state = RuntimeState.READY

    def shutdown(self) -> None:
        self.state = RuntimeState.OFFLINE

    def bind_ephemeral_socket(self) -> socket.socket:
        if self.settings.bind_host != "127.0.0.1":
            raise ValueError("LOCAL_COMPUTE_LOOPBACK_ONLY")
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", self.settings.bind_port))
        listener.listen()
        self.bound_port = int(listener.getsockname()[1])
        return listener

    def set_update_required(self) -> None:
        self.state = RuntimeState.UPDATE_REQUIRED

    def revoke(self) -> None:
        self.sessions.revoke()
        self.state = RuntimeState.REVOKED

    def runtime_info(self) -> dict:
        return {
            "protocol_version": self.settings.protocol_version,
            "runtime_version": self.settings.runtime_version,
            "endpoint_generation": self.endpoint_generation,
            "state": self.state.value,
            "development_mode": self.settings.development_mode,
        }

    def capabilities(self) -> dict:
        return {
            "pdf_processing": "READY",
            "chunking": "READY",
            "embedding": "READY",
            "indexing": "READY",
            "retrieval": "READY",
            "generation": self._generation_capability,
        }

    def update_generation_capability(self, state: str) -> None:
        self._generation_capability = state

    def generation_router(self):
        if self._generation_router is None:
            from app.generation.profile import get_generation_profile
            from .generation import GenerationRouter, LocalGenerationProvider

            provider = LocalGenerationProvider(
                get_generation_profile(),
                self.settings.local_generation_base_url,
                development_mode=self.settings.development_mode,
            )
            self._generation_router = GenerationRouter(provider)
        return self._generation_router
