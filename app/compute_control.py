"""Platform-side, metadata-only ZKD Compute control-plane domain service."""
from __future__ import annotations

import base64, binascii, hashlib, hmac, json, secrets, uuid
from datetime import timedelta

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.auth import utcnow
from app.models.compute_control import ComputeDevice, ComputeLocalSessionGrant, ComputePairingChallenge, ComputePresence, ComputeReplayNonce, LocalDocumentManifest

CAPABILITIES = {"pdf_processing", "chunking", "embedding", "indexing", "retrieval", "generation"}
STATES = {"OFFLINE", "CONNECTING", "AUTHENTICATING", "READY", "BUSY", "DEGRADED", "UNAVAILABLE", "REVOKED", "UPDATE_REQUIRED"}
FORBIDDEN_MANIFEST_FIELDS = {"pdf_bytes", "page_text", "reconstructed_text", "chunk_text", "chunks", "embedding", "embeddings", "vector", "prompt", "context", "answer", "query", "credential", "secret", "private_key"}
CONTROL_PROTOCOL_VERSION = "zkd-compute-v1"


class ComputeControlError(Exception):
    def __init__(self, code: str, message: str | None = None): self.code, self.message = code, message or code.replace("_", " ").title(); super().__init__(self.message)


def _hash(value: str) -> str: return hashlib.sha256(value.encode()).hexdigest()
def _canonical(method: str, path: str, epoch: int, timestamp: str, nonce: str, body: bytes) -> bytes:
    return "|".join((method.upper(), path, str(epoch), timestamp, nonce, hashlib.sha256(body).hexdigest())).encode()


class ComputeControlService:
    def __init__(self, db: Session, *, grant_key: str, pairing_ttl_seconds: int = 300, grant_ttl_seconds: int = 300, auth_window_seconds: int = 300, presence_ttl_seconds: int = 90):
        self.db, self.grant_key = db, grant_key
        self.pairing_ttl_seconds, self.grant_ttl_seconds, self.auth_window_seconds, self.presence_ttl_seconds = pairing_ttl_seconds, grant_ttl_seconds, auth_window_seconds, presence_ttl_seconds

    def create_pairing(self, owner_user_id):
        raw, code = secrets.token_urlsafe(32), f"{secrets.randbelow(1_000_000):06d}"
        now = utcnow(); item = ComputePairingChallenge(owner_user_id=owner_user_id, token_hash=_hash(raw), confirmation_code_hash=_hash(code), state="PENDING", expires_at=now + timedelta(seconds=self.pairing_ttl_seconds))
        self.db.add(item); self.db.commit()
        return item, raw, code

    def complete_pairing(self, challenge_id, token: str, public_key_b64: str, signature_b64: str, protocol_version: str, runtime_version: str, label: str | None):
        item = self.db.get(ComputePairingChallenge, challenge_id); now = utcnow()
        if item is None or item.token_hash != _hash(token): raise ComputeControlError("PAIRING_INVALID")
        if item.expires_at <= now: item.state = "EXPIRED"; self.db.commit(); raise ComputeControlError("PAIRING_EXPIRED")
        if item.state != "PENDING": raise ComputeControlError("PAIRING_ALREADY_CONSUMED")
        if protocol_version != CONTROL_PROTOCOL_VERSION or not runtime_version:
            raise ComputeControlError("PROTOCOL_VERSION_UNSUPPORTED")
        try:
            key = base64.b64decode(public_key_b64, validate=True); signature = base64.b64decode(signature_b64, validate=True)
            Ed25519PublicKey.from_public_bytes(key).verify(signature, f"pairing|{challenge_id}|{token}".encode())
        except (ValueError, TypeError, binascii.Error, InvalidSignature): raise ComputeControlError("DEVICE_AUTH_INVALID")
        device = ComputeDevice(owner_user_id=item.owner_user_id, public_key=public_key_b64, friendly_label=label, protocol_version=protocol_version, runtime_version=runtime_version)
        self.db.add(device); self.db.flush(); item.pending_device_id=device.id; item.state="AWAITING_CONFIRMATION"; self.db.commit(); return device

    def confirm_pairing(self, owner_user_id, challenge_id, code: str):
        item = self.db.get(ComputePairingChallenge, challenge_id); now = utcnow()
        if item is None or item.owner_user_id != owner_user_id: raise ComputeControlError("PAIRING_INVALID")
        if item.expires_at <= now: item.state="EXPIRED"; self.db.commit(); raise ComputeControlError("PAIRING_EXPIRED")
        if item.state != "AWAITING_CONFIRMATION" or not hmac.compare_digest(item.confirmation_code_hash, _hash(code)): raise ComputeControlError("PAIRING_INVALID")
        item.state="CONSUMED"; item.confirmed_at=item.consumed_at=now; self.db.commit(); return self.db.get(ComputeDevice, item.pending_device_id)

    def _device_auth(self, device_id, epoch: int, timestamp: str, nonce: str, signature_b64: str, method: str, path: str, body: bytes) -> ComputeDevice:
        device = self.db.get(ComputeDevice, device_id); now = utcnow()
        if device is None: raise ComputeControlError("DEVICE_NOT_FOUND")
        if device.revoked_at: raise ComputeControlError("DEVICE_REVOKED")
        if device.credential_epoch != epoch: raise ComputeControlError("DEVICE_AUTH_INVALID")
        try:
            observed = int(timestamp)
            if abs(now.timestamp() - observed) > self.auth_window_seconds: raise ValueError
            key = Ed25519PublicKey.from_public_bytes(base64.b64decode(device.public_key, validate=True))
            key.verify(base64.b64decode(signature_b64, validate=True), _canonical(method, path, epoch, timestamp, nonce, body))
        except (ValueError, TypeError, binascii.Error, InvalidSignature): raise ComputeControlError("DEVICE_AUTH_INVALID")
        nonce_hash = _hash(nonce); self.db.execute(delete(ComputeReplayNonce).where(ComputeReplayNonce.expires_at < now))
        if self.db.get(ComputeReplayNonce, (device.id, nonce_hash)): raise ComputeControlError("DEVICE_REPLAY_DETECTED")
        self.db.add(ComputeReplayNonce(device_id=device.id, nonce_hash=nonce_hash, expires_at=now + timedelta(seconds=self.auth_window_seconds))); self.db.commit(); return device

    def authenticate_device(self, **kwargs): return self._device_auth(**kwargs)

    def publish_presence(self, device, payload: dict):
        allowed = {"state", "protocol_version", "runtime_version", "endpoint_generation", "endpoint_port", "capabilities", "provider_metadata"}
        if set(payload) - allowed or payload.get("protocol_version") != CONTROL_PROTOCOL_VERSION or not payload.get("runtime_version"):
            raise ComputeControlError("PROTOCOL_VERSION_UNSUPPORTED")
        if payload.get("state") not in STATES or payload.get("state") == "REVOKED": raise ComputeControlError("MANIFEST_INVALID")
        caps = payload.get("capabilities", {})
        if not isinstance(caps, dict) or not set(caps).issubset(CAPABILITIES): raise ComputeControlError("MANIFEST_INVALID")
        provider_metadata = payload.get("provider_metadata", {})
        if not isinstance(provider_metadata, dict) or FORBIDDEN_MANIFEST_FIELDS & set(provider_metadata): raise ComputeControlError("FORBIDDEN_MANIFEST_CONTENT")
        if not isinstance(payload.get("endpoint_generation"), str) or not payload["endpoint_generation"]:
            raise ComputeControlError("MANIFEST_INVALID")
        port = payload.get("endpoint_port")
        if port is not None and (not isinstance(port, int) or not 0 < port < 65536): raise ComputeControlError("MANIFEST_INVALID")
        item = self.db.get(ComputePresence, device.id) or ComputePresence(device_id=device.id, state="OFFLINE", protocol_version="", runtime_version="", endpoint_generation="", capabilities_json={}, provider_metadata_json={})
        item.state, item.protocol_version, item.runtime_version = payload["state"], payload["protocol_version"], payload["runtime_version"]
        item.endpoint_generation, item.endpoint_port, item.capabilities_json = payload["endpoint_generation"], port, caps
        item.provider_metadata_json, item.last_seen_at = provider_metadata, utcnow(); self.db.add(item); self.db.commit(); return item

    def upsert_manifest(self, device, payload: dict):
        if FORBIDDEN_MANIFEST_FIELDS & set(payload): raise ComputeControlError("FORBIDDEN_MANIFEST_CONTENT")
        allowed = {"document_id","filename","size_bytes","preparation_state","index_state","chunk_count","artifact_id","artifact_version","artifact_profile_fingerprint","local_availability","error_code","error_message"}
        if set(payload) - allowed or not {"document_id","preparation_state","index_state","local_availability"}.issubset(payload): raise ComputeControlError("MANIFEST_INVALID")
        try: document_id = uuid.UUID(str(payload["document_id"]))
        except ValueError: raise ComputeControlError("MANIFEST_INVALID")
        item = self.db.scalar(select(LocalDocumentManifest).where(LocalDocumentManifest.owner_user_id==device.owner_user_id, LocalDocumentManifest.device_id==device.id, LocalDocumentManifest.document_id==document_id))
        values={k: payload.get(k) for k in allowed if k != "document_id"}; values["updated_at"]=utcnow()
        if item is None: item=LocalDocumentManifest(owner_user_id=device.owner_user_id,device_id=device.id,document_id=document_id,**values); self.db.add(item)
        else:
            for key,value in values.items(): setattr(item,key,value)
        self.db.commit(); return item

    def revoke(self, owner_user_id, device_id):
        device=self.db.get(ComputeDevice,device_id)
        if device is None or device.owner_user_id != owner_user_id: raise ComputeControlError("DEVICE_NOT_FOUND")
        if not device.revoked_at: device.revoked_at=utcnow(); device.credential_epoch+=1; self.db.commit()
        return device

    def device_state(self, owner_user_id, device):
        if device.owner_user_id != owner_user_id: raise ComputeControlError("DEVICE_NOT_FOUND")
        presence=self.db.get(ComputePresence,device.id); state="REVOKED" if device.revoked_at else ("OFFLINE" if not presence or presence.last_seen_at < utcnow()-timedelta(seconds=self.presence_ttl_seconds) else presence.state)
        return {"device_id":str(device.id),"friendly_label":device.friendly_label,"credential_epoch":device.credential_epoch,"state":state,"protocol_version":device.protocol_version,"runtime_version":device.runtime_version,"endpoint_generation":presence.endpoint_generation if presence else None,"endpoint_port":presence.endpoint_port if presence and state!="OFFLINE" else None,"capabilities":presence.capabilities_json if presence else {}}

    def manifest_read_model(self, owner_user_id, manifest):
        if manifest.owner_user_id != owner_user_id:
            raise ComputeControlError("DEVICE_NOT_FOUND")
        device = self.db.get(ComputeDevice, manifest.device_id)
        state = self.device_state(owner_user_id, device)
        capabilities = state["capabilities"]
        retrieval_admitted = capabilities.get("retrieval") in {"READY", "ADMITTED"}
        artifact_compatible = bool(manifest.artifact_id and manifest.artifact_profile_fingerprint)
        queryable = all((state["state"] == "READY", retrieval_admitted, manifest.preparation_state == "READY", manifest.index_state == "READY", manifest.local_availability == "AVAILABLE", artifact_compatible))
        return {"document_id":str(manifest.document_id),"device_id":str(manifest.device_id),"preparation_state":manifest.preparation_state,"index_state":manifest.index_state,"local_availability":manifest.local_availability,"artifact_id":str(manifest.artifact_id) if manifest.artifact_id else None,"artifact_profile_fingerprint":manifest.artifact_profile_fingerprint,"device_state":state["state"],"retrieval_admitted":retrieval_admitted,"artifact_compatible":artifact_compatible,"queryable":queryable,"generation_available":capabilities.get("generation") in {"READY", "ADMITTED"}}

    def issue_grant(self, owner_user_id, device_id, browser_nonce: str, origin: str):
        device=self.db.get(ComputeDevice,device_id)
        if device is None or device.owner_user_id != owner_user_id: raise ComputeControlError("DEVICE_NOT_FOUND")
        state=self.device_state(owner_user_id,device)
        if state["state"] != "READY": raise ComputeControlError("DEVICE_OFFLINE")
        if not browser_nonce:
            raise ComputeControlError("LOCAL_SESSION_GRANT_UNAVAILABLE")
        if not self.grant_key: raise ComputeControlError("LOCAL_SESSION_GRANT_UNAVAILABLE")
        try:
            signing_key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(self.grant_key, validate=True))
        except (ValueError, TypeError, binascii.Error):
            raise ComputeControlError("LOCAL_SESSION_GRANT_UNAVAILABLE")
        now=utcnow(); grant=ComputeLocalSessionGrant(owner_user_id=owner_user_id,device_id=device.id,credential_epoch=device.credential_epoch,endpoint_generation=state["endpoint_generation"],origin=origin,browser_nonce_hash=_hash(browser_nonce),expires_at=now+timedelta(seconds=self.grant_ttl_seconds)); self.db.add(grant); self.db.commit()
        claims={"grant_id":str(grant.id),"user_id":str(owner_user_id),"device_id":str(device.id),"credential_epoch":device.credential_epoch,"endpoint_generation":grant.endpoint_generation,"origin":origin,"browser_nonce":browser_nonce,"operations":["documents","jobs","retrieval","answer"],"exp":int(grant.expires_at.timestamp())}
        raw=base64.urlsafe_b64encode(json.dumps(claims,separators=(",",":"),sort_keys=True).encode()).decode().rstrip("=")
        signature=base64.urlsafe_b64encode(signing_key.sign(raw.encode())).decode().rstrip("=")
        return f"{raw}.{signature}", claims

    @staticmethod
    def verify_grant_signature(grant: str, public_key_b64: str) -> dict:
        """P2C.5B-compatible public verification helper; does not consume a grant."""
        try:
            encoded_claims, encoded_signature = grant.split(".", 1)
            padding = "=" * (-len(encoded_signature) % 4)
            signature = base64.urlsafe_b64decode(encoded_signature + padding)
            public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64, validate=True))
            public_key.verify(signature, encoded_claims.encode())
            claim_padding = "=" * (-len(encoded_claims) % 4)
            return json.loads(base64.urlsafe_b64decode(encoded_claims + claim_padding))
        except (ValueError, TypeError, binascii.Error, InvalidSignature, json.JSONDecodeError):
            raise ComputeControlError("LOCAL_SESSION_GRANT_UNAVAILABLE")
