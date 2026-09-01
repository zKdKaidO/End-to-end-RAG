"""Metadata-only manifest synchronization boundary for later platform wiring."""

from __future__ import annotations

from typing import Protocol


class ManifestSyncClient(Protocol):
    """Future implementations may send control metadata only, never RAG content."""

    def publish_metadata_event(self, event_type: str, metadata: dict) -> None:
        ...


class UnavailableManifestSyncClient:
    """Phase A has no cloud control-plane dependency or network side effect."""

    def publish_metadata_event(self, event_type: str, metadata: dict) -> None:
        raise RuntimeError("MANIFEST_SYNC_UNAVAILABLE")
