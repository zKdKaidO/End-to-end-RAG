"""Memory-only browser-local session and per-request MAC validation."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import uuid
import threading
from dataclasses import dataclass

from .errors import LocalComputeError, LocalComputeErrorCode


def canonical_request_transcript(
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body: bytes,
) -> bytes:
    """Return the P2C.4A request proof transcript for an exact HTTP request."""
    body_hash = hashlib.sha256(body).hexdigest()
    return "|".join((method.upper(), path, timestamp, nonce, body_hash)).encode("utf-8")


def request_mac(
    session_key: str,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body: bytes,
) -> str:
    return hmac.new(
        session_key.encode("utf-8"),
        canonical_request_transcript(method, path, timestamp, nonce, body),
        hashlib.sha256,
    ).hexdigest()


@dataclass
class LocalSession:
    session_id: str
    session_key: str
    origin: str
    expires_at: int
    used_nonces: dict[str, int]
    user_id: str | None = None
    device_id: str | None = None
    credential_epoch: int | None = None
    endpoint_generation: str | None = None
    browser_nonce: str | None = None
    allowed_operations: frozenset[str] = frozenset()


class GrantVerifier:
    def verify(self, grant: str, origin: str) -> None:
        raise NotImplementedError


class UnavailableGrantVerifier(GrantVerifier):
    def verify(self, grant: str, origin: str) -> None:
        raise LocalComputeError(LocalComputeErrorCode.NOT_PAIRED, "Pairing verification is unavailable.")


class DevelopmentGrantVerifier(GrantVerifier):
    """Explicitly non-production test verifier; no package default enables it."""

    def verify(self, grant: str, origin: str) -> None:
        if not hmac.compare_digest(grant, "development-test-grant"):
            raise LocalComputeError(LocalComputeErrorCode.AUTH_INVALID, "Invalid development grant.")


class LocalSessionManager:
    def __init__(self, session_lifetime_seconds: int, nonce_lifetime_seconds: int):
        self._session_lifetime_seconds = session_lifetime_seconds
        self._nonce_lifetime_seconds = nonce_lifetime_seconds
        self._sessions: dict[str, LocalSession] = {}
        self._revoked = False
        self._lock = threading.Lock()

    def create_session(self, origin: str, *, user_id: str | None = None, device_id: str | None = None, credential_epoch: int | None = None, endpoint_generation: str | None = None, browser_nonce: str | None = None, allowed_operations: frozenset[str] = frozenset()) -> LocalSession:
        now = int(time.time())
        session = LocalSession(
            session_id=str(uuid.uuid4()),
            session_key=secrets.token_urlsafe(32),
            origin=origin,
            expires_at=now + self._session_lifetime_seconds,
            used_nonces={},
            user_id=user_id, device_id=device_id, credential_epoch=credential_epoch,
            endpoint_generation=endpoint_generation, browser_nonce=browser_nonce,
            allowed_operations=allowed_operations,
        )
        self._sessions[session.session_id] = session
        return session

    def revoke(self) -> None:
        self._revoked = True
        self._sessions.clear()

    def invalidate_all(self) -> None:
        self._sessions.clear()

    def validate(self, method: str, path: str, body: bytes, origin: str, headers, operation: str | None = None) -> LocalSession:
        if self._revoked:
            raise LocalComputeError(LocalComputeErrorCode.NOT_PAIRED, "Device is revoked.")
        session_id = headers.get("X-ZKD-Local-Session")
        timestamp = headers.get("X-ZKD-Timestamp")
        nonce = headers.get("X-ZKD-Nonce")
        mac = headers.get("X-ZKD-MAC")
        if not all((session_id, timestamp, nonce, mac)):
            raise LocalComputeError(LocalComputeErrorCode.AUTH_REQUIRED)
        now = int(time.time())
        try:
            request_time = int(timestamp)
        except ValueError as exc:
            raise LocalComputeError(LocalComputeErrorCode.AUTH_INVALID, "Invalid timestamp.") from exc
        if abs(now - request_time) > self._nonce_lifetime_seconds:
            raise LocalComputeError(LocalComputeErrorCode.SESSION_EXPIRED, "Request timestamp expired.")
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or now >= session.expires_at:
                self._sessions.pop(session_id, None)
                raise LocalComputeError(LocalComputeErrorCode.SESSION_EXPIRED)
            if origin != session.origin:
                raise LocalComputeError(LocalComputeErrorCode.AUTH_INVALID, "Session origin does not match.")
            self._purge_nonces(session, now)
            if nonce in session.used_nonces:
                raise LocalComputeError(LocalComputeErrorCode.REPLAY_DETECTED)
            expected = request_mac(session.session_key, method, path, timestamp, nonce, body)
            if not hmac.compare_digest(mac, expected):
                raise LocalComputeError(LocalComputeErrorCode.AUTH_INVALID, "Request proof is invalid.")
            if operation and session.allowed_operations and operation not in session.allowed_operations:
                raise LocalComputeError(LocalComputeErrorCode.OPERATION_NOT_ALLOWED)
            session.used_nonces[nonce] = now + self._nonce_lifetime_seconds
        return session

    def _purge_nonces(self, session: LocalSession, now: int) -> None:
        for nonce, expires_at in list(session.used_nonces.items()):
            if expires_at <= now:
                session.used_nonces.pop(nonce, None)
