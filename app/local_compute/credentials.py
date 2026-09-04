"""Device private-key boundary for the outbound platform control channel.

Production deliberately has no plaintext fallback. The temporary file store
is test-only and must be constructed explicitly by tests or development tools.
"""

from __future__ import annotations

import base64
import ctypes
import os
from ctypes import wintypes
from pathlib import Path
from typing import Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .errors import LocalComputeError, LocalComputeErrorCode


class DeviceCredentialStore(Protocol):
    def load_private_key(self) -> Ed25519PrivateKey | None: ...
    def save_private_key(self, key: Ed25519PrivateKey) -> None: ...


class UnavailableDeviceCredentialStore:
    """Production fail-closed placeholder when secure credential storage is unavailable."""

    def load_private_key(self) -> Ed25519PrivateKey | None:
        raise LocalComputeError(
            LocalComputeErrorCode.CREDENTIAL_STORE_UNAVAILABLE
        )

    def save_private_key(self, key: Ed25519PrivateKey) -> None:
        raise LocalComputeError(
            LocalComputeErrorCode.CREDENTIAL_STORE_UNAVAILABLE
        )


class TemporaryFileDeviceCredentialStore:
    """Explicitly test/development-only isolated plaintext key storage."""

    def __init__(self, path: Path):
        self.path = path

    def load_private_key(self) -> Ed25519PrivateKey | None:
        if not self.path.exists():
            return None

        try:
            raw = base64.b64decode(
                self.path.read_bytes(),
                validate=True,
            )
            return Ed25519PrivateKey.from_private_bytes(raw)
        except Exception as exc:
            raise LocalComputeError(
                LocalComputeErrorCode.CREDENTIAL_STORE_UNAVAILABLE
            ) from exc

    def save_private_key(self, key: Ed25519PrivateKey) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(
            base64.b64encode(key.private_bytes_raw())
        )


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _require_windows() -> None:
    if os.name != "nt":
        raise LocalComputeError(
            LocalComputeErrorCode.CREDENTIAL_STORE_UNAVAILABLE,
            "Windows protected credential storage is unavailable.",
        )


def _input_blob(data: bytes) -> tuple[_DataBlob, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)

    blob = _DataBlob(
        cbData=len(data),
        pbData=ctypes.cast(
            buffer,
            ctypes.POINTER(ctypes.c_byte),
        ),
    )

    return blob, buffer


def _configure_dpapi():
    _require_windows()

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL

    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL

    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    return crypt32, kernel32


def _dpapi_protect(data: bytes) -> bytes:
    crypt32, kernel32 = _configure_dpapi()

    source, source_buffer = _input_blob(data)
    result = _DataBlob()

    success = crypt32.CryptProtectData(
        ctypes.byref(source),
        "ZKD Compute device identity",
        None,
        None,
        None,
        0x01,  # CRYPTPROTECT_UI_FORBIDDEN
        ctypes.byref(result),
    )

    if not success:
        raise LocalComputeError(
            LocalComputeErrorCode.CREDENTIAL_STORE_UNAVAILABLE,
            "Windows DPAPI failed to protect the device credential.",
        )

    try:
        return ctypes.string_at(
            result.pbData,
            result.cbData,
        )
    finally:
        if result.pbData:
            kernel32.LocalFree(
                ctypes.cast(
                    result.pbData,
                    ctypes.c_void_p,
                )
            )

        # Keep the backing input buffer alive until DPAPI has returned.
        _ = source_buffer


def _dpapi_unprotect(data: bytes) -> bytes:
    crypt32, kernel32 = _configure_dpapi()

    source, source_buffer = _input_blob(data)
    result = _DataBlob()

    success = crypt32.CryptUnprotectData(
        ctypes.byref(source),
        None,
        None,
        None,
        None,
        0x01,  # CRYPTPROTECT_UI_FORBIDDEN
        ctypes.byref(result),
    )

    if not success:
        raise LocalComputeError(
            LocalComputeErrorCode.CREDENTIAL_STORE_UNAVAILABLE,
            "Windows DPAPI failed to unlock the device credential.",
        )

    try:
        return ctypes.string_at(
            result.pbData,
            result.cbData,
        )
    finally:
        if result.pbData:
            kernel32.LocalFree(
                ctypes.cast(
                    result.pbData,
                    ctypes.c_void_p,
                )
            )

        _ = source_buffer


class WindowsDpapiDeviceCredentialStore:
    """Persistent Windows user-bound storage for the device private key.

    The Ed25519 private key is encrypted with Windows DPAPI before being
    persisted. The encrypted credential can normally only be decrypted by the
    same Windows user account on the same Windows installation.
    """

    def __init__(self, path: Path):
        self.path = path

    def load_private_key(self) -> Ed25519PrivateKey | None:
        if not self.path.exists():
            return None

        try:
            protected = self.path.read_bytes()

            if not protected:
                raise ValueError("Empty credential file.")

            raw = _dpapi_unprotect(protected)

            if len(raw) != 32:
                raise ValueError(
                    "Invalid Ed25519 private-key length."
                )

            return Ed25519PrivateKey.from_private_bytes(raw)

        except LocalComputeError:
            raise

        except Exception as exc:
            raise LocalComputeError(
                LocalComputeErrorCode.CREDENTIAL_STORE_UNAVAILABLE,
                "Stored device credential is invalid or unavailable.",
            ) from exc

    def save_private_key(self, key: Ed25519PrivateKey) -> None:
        try:
            self.path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            raw = key.private_bytes_raw()
            protected = _dpapi_protect(raw)

            temporary = self.path.with_name(
                f"{self.path.name}.tmp"
            )

            try:
                with temporary.open("wb") as handle:
                    handle.write(protected)
                    handle.flush()
                    os.fsync(handle.fileno())

                os.replace(
                    temporary,
                    self.path,
                )

            finally:
                if temporary.exists():
                    temporary.unlink()

        except LocalComputeError:
            raise

        except Exception as exc:
            raise LocalComputeError(
                LocalComputeErrorCode.CREDENTIAL_STORE_UNAVAILABLE,
                "Unable to persist the protected device credential.",
            ) from exc


def public_key_b64(key: Ed25519PrivateKey) -> str:
    return base64.b64encode(
        key.public_key().public_bytes_raw()
    ).decode("ascii")