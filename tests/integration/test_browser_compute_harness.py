"""P2C.5C.1A browser-like integration harness; no production frontend involved."""
from __future__ import annotations

import base64
import json
import uuid
from datetime import timedelta

import pymupdf
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.auth.passwords import hash_password
from app.compute_control import ComputeControlError, ComputeControlService
from app.db.database import SessionLocal
from app.local_compute.api import create_local_compute_app
from app.local_compute.credentials import TemporaryFileDeviceCredentialStore, public_key_b64
from app.local_compute.grants import PlatformGrantVerificationKeyProvider, PlatformGrantVerifier
from app.local_compute.runtime import LocalComputeRuntime
from app.local_compute.settings import LocalComputeSettings
from app.models.auth import User, UserRole, UserStatus, utcnow
from app.models.compute_control import ComputeDevice, ComputeLocalSessionGrant, ComputePairingChallenge, ComputePresence, ComputeReplayNonce, LocalDocumentManifest
from tools.browser_protocol.reference_client import BrowserComputeReferenceClient, create_browser_nonce, serialize_json_once


class ServiceTransport:
    def __init__(self, control): self.control, self.available = control, True
    def send(self, method, path, body, headers):
        if not self.available: return 503, {"error_code": "CONTROL_CHANNEL_UNAVAILABLE"}
        try:
            device = self.control.authenticate_device(device_id=uuid.UUID(headers["X-ZKD-Device-ID"]), epoch=int(headers["X-ZKD-Credential-Epoch"]), timestamp=headers["X-ZKD-Timestamp"], nonce=headers["X-ZKD-Nonce"], signature_b64=headers["X-ZKD-Signature"], method=method, path=path, body=body)
            if path.endswith("presence"): self.control.publish_presence(device, json.loads(body))
            elif path.endswith("manifests"): self.control.upsert_manifest(device, json.loads(body))
            else: return 404, {"error_code": "CONTROL_CHANNEL_UNAVAILABLE"}
            return 200, {}
        except ComputeControlError as error: return 403, {"detail": {"error_code": error.code}}


@pytest.fixture
def harness(tmp_path):
    db = SessionLocal()
    user = User(email=f"{uuid.uuid4()}@browser-harness.invalid", normalized_email=f"{uuid.uuid4()}@browser-harness.invalid", password_hash=hash_password("correct horse battery staple"), role=UserRole.USER.value, status=UserStatus.ACTIVE.value)
    db.add(user); db.commit()
    key = Ed25519PrivateKey.generate()
    store = TemporaryFileDeviceCredentialStore(tmp_path / "device-key"); store.save_private_key(key)
    platform = ComputeControlService(db, grant_key="")
    challenge, token, code = platform.create_pairing(user.id)
    signature = base64.b64encode(key.sign(f"pairing|{challenge.id}|{token}".encode())).decode()
    device = platform.complete_pairing(challenge.id, token, public_key_b64(key), signature, "zkd-compute-v1", "0.1.0", "browser harness")
    platform.confirm_pairing(user.id, challenge.id, code)
    transport = ServiceTransport(platform)
    runtime = LocalComputeRuntime(LocalComputeSettings(data_root=tmp_path / "Compute", development_mode=True, development_origins=("http://localhost:5173",), control_auto_start=False), credential_store=store, control_transport=transport)
    runtime.start(); listener = runtime.bind_ephemeral_socket()
    runtime.control_channel.complete_pairing_state(str(device.id), str(user.id), device.credential_epoch)
    signing = Ed25519PrivateKey.generate()
    platform.grant_key = base64.b64encode(signing.private_bytes_raw()).decode()
    runtime.grant_verifier = PlatformGrantVerifier(runtime, PlatformGrantVerificationKeyProvider(base64.b64encode(signing.public_key().public_bytes_raw()).decode()))
    runtime.control_channel.tick()
    yield db, user, platform, device, runtime, transport, listener
    listener.close(); runtime.shutdown()
    ids = [user.id]
    db.execute(delete(ComputeLocalSessionGrant).where(ComputeLocalSessionGrant.owner_user_id.in_(ids))); db.execute(delete(LocalDocumentManifest).where(LocalDocumentManifest.owner_user_id.in_(ids))); db.execute(delete(ComputePresence).where(ComputePresence.device_id.in_(db.query(ComputeDevice.id).filter(ComputeDevice.owner_user_id.in_(ids))))); db.execute(delete(ComputeReplayNonce).where(ComputeReplayNonce.device_id.in_(db.query(ComputeDevice.id).filter(ComputeDevice.owner_user_id.in_(ids))))); db.execute(delete(ComputePairingChallenge).where(ComputePairingChallenge.owner_user_id.in_(ids))); db.execute(delete(ComputeDevice).where(ComputeDevice.owner_user_id.in_(ids))); db.execute(delete(User).where(User.id.in_(ids))); db.commit(); db.close()


def _bootstrap(platform, user, device, runtime, browser, client):
    browser.accept_discovery(platform.device_state(user.id, device), required_capability="retrieval")
    nonce = create_browser_nonce()
    grant, _ = platform.issue_grant(user.id, device.id, nonce, "https://rag.zkd.id.vn")
    response = client.post("/v1/sessions", headers={"Origin": "https://rag.zkd.id.vn", "X-ZKD-Local-Grant": grant, "X-ZKD-Browser-Nonce": nonce})
    assert response.status_code == 200, response.text
    browser.bootstrap_session(response.json(), required_capability="retrieval")
    return browser.signer()


def _headers(signer, method, path, body):
    return signer.sign(method, path, body)


def _pdf_bytes(text):
    document = pymupdf.open(); page = document.new_page(); page.insert_text((72, 72), text, fontsize=11); result = document.tobytes(); document.close(); return result


def test_browser_like_reference_harness_pdf_query_expiry_generation_offline_revocation_and_update(harness):
    db, user, platform, device, runtime, transport, _ = harness
    client = TestClient(create_local_compute_app(runtime)); browser = BrowserComputeReferenceClient()
    signer = _bootstrap(platform, user, device, runtime, browser, client)

    runtime_path = "/v1/runtime"
    assert client.get(runtime_path, headers=_headers(signer, "GET", runtime_path, b"")).status_code == 200
    document_id = str(uuid.uuid4()); source = _pdf_bytes("NGHỊ ĐỊNH\nĐiều 1. Quy định áp dụng cho doanh nghiệp.")
    source_path = f"/v1/documents/{document_id}/source"
    assert client.put(source_path, content=source, headers={**_headers(signer, "PUT", source_path, source), "Content-Type": "application/pdf", "X-ZKD-Filename": "legal.pdf"}).status_code == 200
    prepare_path = f"/v1/documents/{document_id}/prepare"
    assert client.post(prepare_path, content=b"", headers=_headers(signer, "POST", prepare_path, b"")).status_code == 200
    index_path = f"/v1/documents/{document_id}/index"
    assert client.post(index_path, content=b"", headers=_headers(signer, "POST", index_path, b"")).status_code == 200
    query_path = "/v1/queries"; query_body = serialize_json_once({"query_text": "doanh nghiệp", "document_ids": [document_id]})
    assert client.post(query_path, content=query_body, headers={**_headers(signer, "POST", query_path, query_body), "Content-Type": "application/json"}).status_code == 200

    runtime.sessions._sessions[browser.session.session_id].expires_at = 0
    assert client.get(runtime_path, headers=_headers(signer, "GET", runtime_path, b"")).status_code == 401
    signer = _bootstrap(platform, user, device, runtime, browser, client)

    runtime.recreate_endpoint_generation(); runtime.control_channel.next_attempt_at = 0; runtime.control_channel.tick()
    browser.accept_discovery(platform.device_state(user.id, device), required_capability="retrieval")
    assert browser.session is None
    signer = _bootstrap(platform, user, device, runtime, browser, client)

    presence = db.get(ComputePresence, device.id); presence.last_seen_at = utcnow() - timedelta(seconds=platform.presence_ttl_seconds + 1); db.commit()
    offline = platform.device_state(user.id, device); browser.accept_discovery(offline, required_capability="retrieval")
    assert browser.session is None and browser.state.value == "DEVICE_OFFLINE"
    runtime.control_channel.next_attempt_at = 0; runtime.control_channel.tick()

    signer = _bootstrap(platform, user, device, runtime, browser, client)
    transport.available = False
    assert client.post(query_path, content=query_body, headers={**_headers(signer, "POST", query_path, query_body), "Content-Type": "application/json"}).status_code == 200
    transport.available = True; platform.revoke(user.id, device.id); runtime.control_channel.next_attempt_at = 0; runtime.control_channel.tick()
    assert client.get(runtime_path, headers=_headers(signer, "GET", runtime_path, b"")).status_code == 503
    browser.accept_discovery(platform.device_state(user.id, device), required_capability="retrieval")
    assert browser.state.value == "REVOKED"


def test_update_required_rejects_new_bootstrap(harness):
    _, user, platform, device, runtime, _, _ = harness
    client = TestClient(create_local_compute_app(runtime))
    runtime.set_update_required()
    grant, _ = platform.issue_grant(user.id, device.id, create_browser_nonce(), "https://rag.zkd.id.vn")
    response = client.post("/v1/sessions", headers={"Origin": "https://rag.zkd.id.vn", "X-ZKD-Local-Grant": grant, "X-ZKD-Browser-Nonce": "different"})
    assert response.status_code == 426
    assert response.json()["error"]["code"] == "UPDATE_REQUIRED"
