"""Memory-only browser-local session and per-request MAC validation."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import uuid
from dataclasses import dataclass

from .errors import LocalComputeError, LocalComputeErrorCode


@dataclass
class LocalSession:
    session_id: str
    session_key: str
    origin: str
    expires_at: int
    used_nonces: dict[str, int]


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

    def create_session(self, origin: str) -> LocalSession:
        now = int(time.time())
        session = LocalSession(
            session_id=str(uuid.uuid4()),
            session_key=secrets.token_urlsafe(32),
            origin=origin,
            expires_at=now + self._session_lifetime_seconds,
            used_nonces={},
        )
        self._sessions[session.session_id] = session
        return session

    def revoke(self) -> None:
        self._revoked = True
        self._sessions.clear()

    def validate(self, method: str, path: str, body: bytes, origin: str, headers) -> LocalSession:
        if self._revoked:
            raise LocalComputeError(LocalComputeErrorCode.NOT_PAIRED, "Device is revoked.")
        session_id = headers.get("X-ZKD-Local-Session")
        timestamp = headers.get("X-ZKD-Timestamp")
        nonce = headers.get("X-ZKD-Nonce")
        mac = headers.get("X-ZKD-MAC")
        if not all((session_id, timestamp, nonce, mac)):
            raise LocalComputeError(LocalComputeErrorCode.AUTH_REQUIRED)
        session = self._sessions.get(session_id)
        now = int(time.time())
        if session is None or now >= session.expires_at:
            self._sessions.pop(session_id, None)
            raise LocalComputeError(LocalComputeErrorCode.SESSION_EXPIRED)
        if origin != session.origin:
            raise LocalComputeError(LocalComputeErrorCode.AUTH_INVALID, "Session origin does not match.")
        try:
            request_time = int(timestamp)
        except ValueError as exc:
            raise LocalComputeError(LocalComputeErrorCode.AUTH_INVALID, "Invalid timestamp.") from exc
        if abs(now - request_time) > self._nonce_lifetime_seconds:
            raise LocalComputeError(LocalComputeErrorCode.SESSION_EXPIRED, "Request timestamp expired.")
        self._purge_nonces(session, now)
        if nonce in session.used_nonces:
            raise LocalComputeError(LocalComputeErrorCode.REPLAY_DETECTED)
        body_hash = hashlib.sha256(body).hexdigest()
        payload = "|".join((method.upper(), path, timestamp, nonce, body_hash)).encode("utf-8")
        expected = hmac.new(session.session_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, expected):
            raise LocalComputeError(LocalComputeErrorCode.AUTH_INVALID, "Request proof is invalid.")
        session.used_nonces[nonce] = now + self._nonce_lifetime_seconds
        return session

    def _purge_nonces(self, session: LocalSession, now: int) -> None:
        for nonce, expires_at in list(session.used_nonces.items()):
            if expires_at <= now:
                session.used_nonces.pop(nonce, None)
