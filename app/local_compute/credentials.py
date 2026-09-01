"""Device private-key boundary for the outbound platform control channel.

Production deliberately has no plaintext fallback.  The temporary file store
is test-only and must be constructed explicitly by tests or development tools.
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .errors import LocalComputeError, LocalComputeErrorCode


class DeviceCredentialStore(Protocol):
    def load_private_key(self) -> Ed25519PrivateKey | None: ...
    def save_private_key(self, key: Ed25519PrivateKey) -> None: ...


class UnavailableDeviceCredentialStore:
    """Production fail-closed placeholder until OS-protected storage is wired."""
    def load_private_key(self) -> Ed25519PrivateKey | None:
        raise LocalComputeError(LocalComputeErrorCode.CREDENTIAL_STORE_UNAVAILABLE)

    def save_private_key(self, key: Ed25519PrivateKey) -> None:
        raise LocalComputeError(LocalComputeErrorCode.CREDENTIAL_STORE_UNAVAILABLE)


class TemporaryFileDeviceCredentialStore:
    """Explicitly test/development-only isolated key storage."""
    def __init__(self, path: Path):
        self.path = path

    def load_private_key(self) -> Ed25519PrivateKey | None:
        if not self.path.exists():
            return None
        return Ed25519PrivateKey.from_private_bytes(base64.b64decode(self.path.read_bytes(), validate=True))

    def save_private_key(self, key: Ed25519PrivateKey) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(base64.b64encode(key.private_bytes_raw()))


def public_key_b64(key: Ed25519PrivateKey) -> str:
    return base64.b64encode(key.public_key().public_bytes_raw()).decode()
