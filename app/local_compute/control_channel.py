"""Outbound-only ZKD Compute → Platform metadata control channel."""
from __future__ import annotations

import base64
import json
import random
import secrets
import time
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .credentials import DeviceCredentialStore, public_key_b64
from .errors import LocalComputeError, LocalComputeErrorCode

FORBIDDEN_METADATA_FIELDS = {"pdf_bytes", "page_text", "reconstructed_text", "chunk_text", "chunks", "embedding", "embeddings", "vector", "prompt", "context", "answer", "query", "credential", "secret", "private_key"}


def canonical_device_request(method: str, path: str, epoch: int, timestamp: str, nonce: str, body: bytes) -> bytes:
    """Exact P2C.5A signing transcript; shared contract, not a duplicate variant."""
    import hashlib
    return "|".join((method.upper(), path, str(epoch), timestamp, nonce, hashlib.sha256(body).hexdigest())).encode()


def canonical_json(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


class ControlChannelState(str, Enum):
    DISCONNECTED = "DISCONNECTED"; CONNECTING = "CONNECTING"; CONNECTED = "CONNECTED"; BACKING_OFF = "BACKING_OFF"; REVOKED = "REVOKED"; UPDATE_REQUIRED = "UPDATE_REQUIRED"


@dataclass(frozen=True)
class PairedDeviceState:
    device_id: str; owner_user_id: str | None; credential_epoch: int; platform_base_url: str; protocol_version: str; pairing_state: str = "PAIRED"; revocation_state: str = "ACTIVE"


class ControlTransport(Protocol):
    def send(self, method: str, path: str, body: bytes, headers: dict[str, str]) -> tuple[int, dict]: ...


class PlatformControlClient:
    """Narrow client: it can only perform declared control-plane operations."""
    def __init__(self, transport: ControlTransport, identity: Ed25519PrivateKey, paired: PairedDeviceState, now: Callable[[], float] = time.time):
        self.transport, self.identity, self.paired, self.now = transport, identity, paired, now

    def _send(self, path: str, payload: dict) -> dict:
        body = canonical_json(payload); timestamp = str(int(self.now())); nonce = secrets.token_urlsafe(24)
        signature = base64.b64encode(self.identity.sign(canonical_device_request("POST", path, self.paired.credential_epoch, timestamp, nonce, body))).decode()
        status, response = self.transport.send("POST", path, body, {"Content-Type":"application/json", "X-ZKD-Device-ID":self.paired.device_id, "X-ZKD-Credential-Epoch":str(self.paired.credential_epoch), "X-ZKD-Timestamp":timestamp, "X-ZKD-Nonce":nonce, "X-ZKD-Signature":signature})
        if 200 <= status < 300: return response
        code = response.get("detail", {}).get("error_code") or response.get("error_code") or "CONTROL_CHANNEL_UNAVAILABLE"
        mapping = {"DEVICE_REVOKED":LocalComputeErrorCode.DEVICE_REVOKED, "PROTOCOL_VERSION_UNSUPPORTED":LocalComputeErrorCode.PROTOCOL_VERSION_UNSUPPORTED, "DEVICE_AUTH_INVALID":LocalComputeErrorCode.CREDENTIAL_EPOCH_MISMATCH, "MANIFEST_INVALID":LocalComputeErrorCode.MANIFEST_INVALID, "FORBIDDEN_MANIFEST_CONTENT":LocalComputeErrorCode.FORBIDDEN_MANIFEST_CONTENT}
        raise LocalComputeError(mapping.get(code, LocalComputeErrorCode.CONTROL_CHANNEL_UNAVAILABLE))

    def publish_presence(self, payload: dict) -> dict:
        return self._send("/api/v1/compute/control/presence", payload)

    def publish_manifest(self, payload: dict) -> dict:
        if FORBIDDEN_METADATA_FIELDS & set(payload):
            raise LocalComputeError(LocalComputeErrorCode.FORBIDDEN_MANIFEST_CONTENT)
        return self._send("/api/v1/compute/control/manifests", payload)


class ControlChannel:
    def __init__(self, runtime, credential_store: DeviceCredentialStore, transport: ControlTransport | None = None, now: Callable[[], float] = time.time, jitter: Callable[[], float] = random.random):
        self.runtime, self.credential_store, self.transport, self.now, self.jitter = runtime, credential_store, transport, now, jitter
        self.state = ControlChannelState.DISCONNECTED; self.next_attempt_at = 0.0; self.backoff = runtime.settings.control_backoff_min_seconds
        self._stop_event = threading.Event(); self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None or self.paired_state() is None:
            return
        self._stop_event.clear(); self._thread = threading.Thread(target=self._run, name="zkd-control-channel", daemon=True); self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None: self._thread.join(timeout=2)
        self._thread = None

    def _run(self) -> None:
        while not self._stop_event.is_set() and self.state not in {ControlChannelState.REVOKED, ControlChannelState.UPDATE_REQUIRED}:
            self.tick()
            self._stop_event.wait(min(max(self.next_attempt_at-self.now(), 0.1), self.runtime.settings.control_heartbeat_seconds))

    def paired_state(self) -> PairedDeviceState | None:
        row = self.runtime.catalog.get_paired_device_state()
        return PairedDeviceState(**row) if row else None

    def complete_pairing_state(self, device_id: str, owner_user_id: str | None, credential_epoch: int) -> None:
        key = self.credential_store.load_private_key()
        if key is None: raise LocalComputeError(LocalComputeErrorCode.CREDENTIAL_STORE_UNAVAILABLE)
        self.runtime.catalog.set_paired_device_state(PairedDeviceState(device_id, owner_user_id, credential_epoch, self.runtime.settings.platform_base_url, self.runtime.settings.protocol_version).__dict__)
        if self.runtime.settings.control_auto_start: self.start()

    def _client(self) -> PlatformControlClient:
        paired=self.paired_state()
        if paired is None: raise LocalComputeError(LocalComputeErrorCode.NOT_PAIRED)
        key=self.credential_store.load_private_key()
        if key is None or self.transport is None: raise LocalComputeError(LocalComputeErrorCode.CONTROL_CHANNEL_UNAVAILABLE)
        return PlatformControlClient(self.transport,key,paired,self.now)

    def presence_payload(self) -> dict:
        return {"state":self.runtime.state.value,"protocol_version":self.runtime.settings.protocol_version,"runtime_version":self.runtime.settings.runtime_version,"endpoint_generation":self.runtime.endpoint_generation,"endpoint_port":self.runtime.bound_port,"capabilities":self.runtime.capabilities(),"provider_metadata":{"LOCAL":self.runtime.capabilities()["generation"],"USER_CLOUD":"NOT_CONFIGURED","PLATFORM_CLOUD":"DISABLED"}}

    def enqueue_manifest(self, payload: dict) -> None:
        if FORBIDDEN_METADATA_FIELDS & set(payload): raise LocalComputeError(LocalComputeErrorCode.FORBIDDEN_MANIFEST_CONTENT)
        required={"document_id","preparation_state","index_state","local_availability"}
        if set(payload) - {"document_id","filename","size_bytes","preparation_state","index_state","chunk_count","artifact_id","artifact_version","artifact_profile_fingerprint","local_availability","error_code","error_message"} or not required.issubset(payload): raise LocalComputeError(LocalComputeErrorCode.MANIFEST_INVALID)
        self.runtime.catalog.enqueue_control_manifest(payload, int(self.now()))

    def tick(self) -> None:
        if self.state in {ControlChannelState.REVOKED, ControlChannelState.UPDATE_REQUIRED} or self.now() < self.next_attempt_at: return
        self.state=ControlChannelState.CONNECTING
        try:
            client=self._client(); client.publish_presence(self.presence_payload())
            for row in self.runtime.catalog.pending_control_manifests():
                client.publish_manifest(row["payload"]); self.runtime.catalog.mark_control_manifest_delivered(row["document_id"], int(self.now()))
            self.state=ControlChannelState.CONNECTED; self.backoff=self.runtime.settings.control_backoff_min_seconds; self.next_attempt_at=self.now()+self.runtime.settings.control_heartbeat_seconds
        except LocalComputeError as exc:
            if exc.code in {LocalComputeErrorCode.DEVICE_REVOKED, LocalComputeErrorCode.CREDENTIAL_EPOCH_MISMATCH}:
                self.state=ControlChannelState.REVOKED; self.runtime.revoke(); return
            if exc.code == LocalComputeErrorCode.PROTOCOL_VERSION_UNSUPPORTED:
                self.state=ControlChannelState.UPDATE_REQUIRED; self.runtime.set_update_required(); return
            self.state=ControlChannelState.BACKING_OFF; self.next_attempt_at=self.now()+self.backoff*(1+self.jitter()*0.2); self.backoff=min(self.backoff*2,self.runtime.settings.control_backoff_max_seconds)
