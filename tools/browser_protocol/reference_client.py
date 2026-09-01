"""Non-product browser-compute protocol reference used only by tests and documentation."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


PRODUCT_ORIGIN = "https://rag.zkd.id.vn"
PROTOCOL_VERSION = "zkd-compute-v1"


class BrowserComputeState(str, Enum):
    NO_DEVICE = "NO_DEVICE"
    DEVICE_OFFLINE = "DEVICE_OFFLINE"
    CONNECTING = "CONNECTING"
    READY = "READY"
    BUSY = "BUSY"
    DEGRADED = "DEGRADED"
    UPDATE_REQUIRED = "UPDATE_REQUIRED"
    REVOKED = "REVOKED"
    SESSION_REQUIRED = "SESSION_REQUIRED"
    SESSION_READY = "SESSION_READY"


class BrowserComputeProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class DeviceDiscovery:
    device_id: str
    state: str
    protocol_version: str
    runtime_version: str
    endpoint_generation: str | None
    endpoint_port: int | None
    capabilities: dict[str, str]

    @classmethod
    def from_platform(cls, payload: dict[str, Any]) -> "DeviceDiscovery":
        return cls(
            device_id=str(payload["device_id"]),
            state=str(payload["state"]),
            protocol_version=str(payload["protocol_version"]),
            runtime_version=str(payload["runtime_version"]),
            endpoint_generation=payload.get("endpoint_generation"),
            endpoint_port=payload.get("endpoint_port"),
            capabilities=dict(payload.get("capabilities") or {}),
        )

    def local_base_url(self, required_capability: str) -> str:
        if self.state == "REVOKED":
            raise BrowserComputeProtocolError("DEVICE_REVOKED")
        if self.state != "READY":
            raise BrowserComputeProtocolError("DEVICE_OFFLINE")
        if self.protocol_version != PROTOCOL_VERSION or not self.runtime_version:
            raise BrowserComputeProtocolError("PROTOCOL_VERSION_UNSUPPORTED")
        if not self.endpoint_generation:
            raise BrowserComputeProtocolError("ENDPOINT_GENERATION_UNAVAILABLE")
        if not isinstance(self.endpoint_port, int) or not 0 < self.endpoint_port < 65536:
            raise BrowserComputeProtocolError("LOOPBACK_ENDPOINT_UNAVAILABLE")
        if self.capabilities.get(required_capability) not in {"READY", "ADMITTED"}:
            raise BrowserComputeProtocolError("CAPABILITY_UNAVAILABLE")
        return f"http://127.0.0.1:{self.endpoint_port}"


@dataclass(frozen=True)
class BrowserLocalSession:
    device_id: str
    endpoint_generation: str
    base_url: str
    session_id: str
    session_secret: str
    expires_at: int
    allowed_operations: frozenset[str]
    protocol_version: str


def create_browser_nonce() -> str:
    """Web Crypto equivalent requirement: fresh CSPRNG output for each bootstrap."""
    return secrets.token_urlsafe(32)


def canonical_transcript(method: str, path: str, timestamp: str, nonce: str, raw_body: bytes) -> str:
    return "|".join((method.upper(), path, timestamp, nonce, hashlib.sha256(raw_body).hexdigest()))


def request_mac(session_secret: str, method: str, path: str, timestamp: str, nonce: str, raw_body: bytes) -> str:
    return hmac.new(session_secret.encode("utf-8"), canonical_transcript(method, path, timestamp, nonce, raw_body).encode("utf-8"), hashlib.sha256).hexdigest()


def serialize_json_once(payload: dict[str, Any]) -> bytes:
    """The returned UTF-8 bytes are both signed and transmitted without reconstruction."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class BrowserComputeRequestSigner:
    def __init__(self, session: BrowserLocalSession, *, clock: Callable[[], float] = time.time, nonce_factory: Callable[[], str] = create_browser_nonce):
        self._session = session
        self._clock = clock
        self._nonce_factory = nonce_factory

    def sign(self, method: str, path: str, raw_body: bytes) -> dict[str, str]:
        if not path.startswith("/") or "?" in path or "#" in path:
            raise BrowserComputeProtocolError("PATH_MUST_BE_EXACT_PATH")
        timestamp = str(int(self._clock()))
        nonce = self._nonce_factory()
        return {
            "Origin": PRODUCT_ORIGIN,
            "X-ZKD-Local-Session": self._session.session_id,
            "X-ZKD-Timestamp": timestamp,
            "X-ZKD-Nonce": nonce,
            "X-ZKD-MAC": request_mac(self._session.session_secret, method, path, timestamp, nonce, raw_body),
            "X-ZKD-Protocol-Version": self._session.protocol_version,
        }


class BrowserComputeReferenceClient:
    """Process-memory-only discovery/session state; no storage or network side effects."""

    def __init__(self):
        self.discovery: DeviceDiscovery | None = None
        self.session: BrowserLocalSession | None = None
        self.state = BrowserComputeState.NO_DEVICE

    def accept_discovery(self, payload: dict[str, Any], *, required_capability: str) -> DeviceDiscovery:
        discovery = DeviceDiscovery.from_platform(payload)
        if self.session and (self.session.device_id != discovery.device_id or self.session.endpoint_generation != discovery.endpoint_generation):
            self.discard_session()
        self.discovery = discovery
        if discovery.state == "REVOKED":
            self.discard_session()
            self.state = BrowserComputeState.REVOKED
        elif discovery.state != "READY":
            self.discard_session()
            self.state = BrowserComputeState.DEVICE_OFFLINE
        else:
            discovery.local_base_url(required_capability)
            self.state = BrowserComputeState.SESSION_REQUIRED
        return discovery

    def bootstrap_session(self, response: dict[str, Any], *, required_capability: str) -> BrowserLocalSession:
        if self.discovery is None:
            raise BrowserComputeProtocolError("DISCOVERY_REQUIRED")
        base_url = self.discovery.local_base_url(required_capability)
        if response.get("endpoint_generation") != self.discovery.endpoint_generation:
            self.discard_session()
            raise BrowserComputeProtocolError("ENDPOINT_GENERATION_MISMATCH")
        if response.get("protocol_version") != PROTOCOL_VERSION:
            self.discard_session()
            raise BrowserComputeProtocolError("PROTOCOL_VERSION_UNSUPPORTED")
        session = BrowserLocalSession(
            device_id=self.discovery.device_id,
            endpoint_generation=self.discovery.endpoint_generation or "",
            base_url=base_url,
            session_id=str(response["local_session_id"]),
            session_secret=str(response["session_key"]),
            expires_at=int(response["expires_at"]),
            allowed_operations=frozenset(response.get("allowed_operations") or ()),
            protocol_version=str(response["protocol_version"]),
        )
        self.session = session
        self.state = BrowserComputeState.SESSION_READY
        return session

    def signer(self) -> BrowserComputeRequestSigner:
        if self.session is None:
            raise BrowserComputeProtocolError("SESSION_REQUIRED")
        return BrowserComputeRequestSigner(self.session)

    def discard_session(self) -> None:
        self.session = None
        if self.state not in {BrowserComputeState.REVOKED, BrowserComputeState.DEVICE_OFFLINE}:
            self.state = BrowserComputeState.SESSION_REQUIRED

    def handle_local_failure(self, code: str) -> None:
        if code in {"SESSION_EXPIRED", "SESSION_BINDING_INVALID", "ENDPOINT_GENERATION_MISMATCH", "AUTH_REQUIRED", "AUTH_INVALID"}:
            self.discard_session()
        elif code == "UPDATE_REQUIRED":
            self.discard_session()
            self.state = BrowserComputeState.UPDATE_REQUIRED
        elif code in {"NOT_PAIRED", "DEVICE_REVOKED"}:
            self.discard_session()
            self.state = BrowserComputeState.REVOKED
