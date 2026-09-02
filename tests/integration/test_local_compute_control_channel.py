"""Isolated P2C.5B.1 Compute → Platform control-channel acceptance tests."""
from __future__ import annotations

import base64
import json
import time
import uuid

import pytest
import pymupdf
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import delete

from app.auth.passwords import hash_password
from app.compute_control import ComputeControlError, ComputeControlService
from app.db.database import SessionLocal
from app.local_compute.control_channel import ControlChannelState
from app.local_compute.credentials import TemporaryFileDeviceCredentialStore, UnavailableDeviceCredentialStore, public_key_b64
from app.local_compute.errors import LocalComputeError, LocalComputeErrorCode
from app.local_compute.runtime import LocalComputeRuntime, RuntimeState
from app.local_compute.settings import LocalComputeSettings
from app.local_compute.grants import PlatformGrantVerifier, PlatformGrantVerificationKeyProvider
from app.local_compute.api import create_local_compute_app
from app.local_compute.documents import LocalDocumentStore
from app.local_compute.sessions import request_mac
from app.models.auth import User, UserRole, UserStatus
from app.models.compute_control import ComputeDevice, ComputeLocalSessionGrant, ComputePairingChallenge, ComputePresence, ComputeReplayNonce, LocalDocumentManifest


def _pdf_bytes(text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    result = document.tobytes()
    document.close()
    return result


class ServiceTransport:
    """Adapter that deliberately invokes the real P2C.5A verifier/service."""
    def __init__(self, control): self.control=control; self.available=True
    def send(self, method, path, body, headers):
        if not self.available: return 503, {"error_code":"CONTROL_CHANNEL_UNAVAILABLE"}
        try:
            device=self.control.authenticate_device(device_id=uuid.UUID(headers["X-ZKD-Device-ID"]),epoch=int(headers["X-ZKD-Credential-Epoch"]),timestamp=headers["X-ZKD-Timestamp"],nonce=headers["X-ZKD-Nonce"],signature_b64=headers["X-ZKD-Signature"],method=method,path=path,body=body)
            payload=json.loads(body)
            if path.endswith("presence"): self.control.publish_presence(device,payload)
            elif path.endswith("manifests"): self.control.upsert_manifest(device,payload)
            else: return 404,{"error_code":"CONTROL_CHANNEL_UNAVAILABLE"}
            return 200,{}
        except ComputeControlError as exc: return 403,{"detail":{"error_code":exc.code}}


@pytest.fixture
def platform_db():
    db=SessionLocal(); user=User(email=f"{uuid.uuid4()}@control.invalid",normalized_email=f"{uuid.uuid4()}@control.invalid",password_hash=hash_password("correct horse battery staple"),role=UserRole.USER.value,status=UserStatus.ACTIVE.value); db.add(user); db.commit()
    yield db,user
    ids=[user.id]
    db.execute(delete(ComputeLocalSessionGrant).where(ComputeLocalSessionGrant.owner_user_id.in_(ids))); db.execute(delete(LocalDocumentManifest).where(LocalDocumentManifest.owner_user_id.in_(ids))); db.execute(delete(ComputePresence).where(ComputePresence.device_id.in_(db.query(ComputeDevice.id).filter(ComputeDevice.owner_user_id.in_(ids)))))
    db.execute(delete(ComputeReplayNonce).where(ComputeReplayNonce.device_id.in_(db.query(ComputeDevice.id).filter(ComputeDevice.owner_user_id.in_(ids))))); db.execute(delete(ComputePairingChallenge).where(ComputePairingChallenge.owner_user_id.in_(ids))); db.execute(delete(ComputeDevice).where(ComputeDevice.owner_user_id.in_(ids))); db.execute(delete(User).where(User.id.in_(ids))); db.commit(); db.close()


def paired_runtime(tmp_path, db, user):
    key=Ed25519PrivateKey.generate(); store=TemporaryFileDeviceCredentialStore(tmp_path/"test-only-key") ; store.save_private_key(key)
    platform=ComputeControlService(db,grant_key="")
    challenge,token,code=platform.create_pairing(user.id); signature=base64.b64encode(key.sign(f"pairing|{challenge.id}|{token}".encode())).decode()
    device=platform.complete_pairing(challenge.id,token,public_key_b64(key),signature,"zkd-compute-v1","0.1.0","isolated"); platform.confirm_pairing(user.id,challenge.id,code)
    transport=ServiceTransport(platform)
    runtime=LocalComputeRuntime(LocalComputeSettings(data_root=tmp_path/"Compute",development_mode=True,development_origins=("http://localhost:5173",),control_auto_start=False),credential_store=store,control_transport=transport); runtime.start(); runtime.control_channel.complete_pairing_state(str(device.id),str(user.id),device.credential_epoch)
    return runtime,transport,platform,device,store


def test_outbound_presence_manifest_outage_recovery_and_privacy(tmp_path,platform_db):
    db,user=platform_db; runtime,transport,platform,device,store=paired_runtime(tmp_path,db,user)
    try:
        runtime.control_channel.tick(); assert runtime.control_channel.state==ControlChannelState.CONNECTED and db.get(ComputePresence,device.id).state=="READY"
        payload={"document_id":str(uuid.uuid4()),"filename":"metadata.pdf","size_bytes":12,"preparation_state":"READY","index_state":"READY","chunk_count":2,"artifact_id":str(uuid.uuid4()),"artifact_version":"v1","artifact_profile_fingerprint":"a"*64,"local_availability":"AVAILABLE"}
        runtime.control_channel.enqueue_manifest(payload); transport.available=False; runtime.control_channel.next_attempt_at=0; runtime.control_channel.tick(); assert runtime.catalog.pending_control_manifests()
        transport.available=True; runtime.control_channel.next_attempt_at=0; runtime.control_channel.tick(); assert not runtime.catalog.pending_control_manifests() and db.query(LocalDocumentManifest).filter_by(document_id=uuid.UUID(payload["document_id"])).one().filename=="metadata.pdf"
        assert key_private_not_in(runtime.settings.catalog_path.read_bytes(),store.path.read_bytes())
        with pytest.raises(LocalComputeError) as blocked: runtime.control_channel.enqueue_manifest({**payload,"prompt":"secret"})
        assert blocked.value.code==LocalComputeErrorCode.FORBIDDEN_MANIFEST_CONTENT
    finally: runtime.shutdown()


def key_private_not_in(catalog_bytes, key_bytes):
    return key_bytes not in catalog_bytes


def test_revocation_halts_control_but_preserves_local_state(tmp_path,platform_db):
    db,user=platform_db; runtime,transport,platform,device,_=paired_runtime(tmp_path,db,user)
    try:
        runtime.control_channel.tick(); platform.revoke(user.id,device.id); runtime.control_channel.next_attempt_at=0; runtime.control_channel.tick()
        assert runtime.control_channel.state==ControlChannelState.REVOKED and runtime.state==RuntimeState.REVOKED and runtime.settings.catalog_path.exists()
    finally: runtime.shutdown()


def test_local_delete_queues_metadata_tombstone_through_outage_recovery(tmp_path, platform_db):
    db, user = platform_db
    runtime, transport, platform, device, _ = paired_runtime(tmp_path, db, user)
    try:
        runtime.control_channel.tick()
        document_id = str(uuid.uuid4())
        LocalDocumentStore(runtime.settings, runtime.catalog).accept_document(
            document_id,
            [_pdf_bytes("Điều 1. Văn bản cục bộ cần được xóa.")],
            "delete-local.pdf",
            "application/pdf",
        )
        LocalDocumentStore(runtime.settings, runtime.catalog).delete_document(document_id)
        transport.available = False
        runtime.control_channel.next_attempt_at = 0
        runtime.control_channel.tick()
        assert runtime.catalog.pending_control_manifests()
        transport.available = True
        runtime.control_channel.next_attempt_at = 0
        runtime.control_channel.tick()
        manifest = db.query(LocalDocumentManifest).filter_by(document_id=uuid.UUID(document_id)).one()
        assert manifest.preparation_state == "DELETED"
        assert manifest.index_state == "DELETED"
        assert manifest.local_availability == "DELETED"
        assert manifest.chunk_count == 0 and manifest.artifact_id is None
    finally:
        runtime.shutdown()


def test_production_credential_store_fails_closed(tmp_path):
    runtime=LocalComputeRuntime(LocalComputeSettings(data_root=tmp_path/"Compute"),credential_store=UnavailableDeviceCredentialStore()); runtime.start()
    try:
        with pytest.raises(LocalComputeError) as unavailable: runtime.credential_store.load_private_key()
        assert unavailable.value.code==LocalComputeErrorCode.CREDENTIAL_STORE_UNAVAILABLE
    finally: runtime.shutdown()


def test_real_platform_grant_is_consumed_once_and_creates_memory_only_session(tmp_path,platform_db):
    from fastapi.testclient import TestClient
    db,user=platform_db; runtime,_,platform,device,_=paired_runtime(tmp_path,db,user)
    signing=Ed25519PrivateKey.generate(); private=base64.b64encode(signing.private_bytes_raw()).decode(); public=base64.b64encode(signing.public_key().public_bytes_raw()).decode(); platform.grant_key=private
    runtime.control_channel.tick(); runtime.grant_verifier=PlatformGrantVerifier(runtime,PlatformGrantVerificationKeyProvider(public))
    nonce="browser-test-nonce"; grant,claims=platform.issue_grant(user.id,device.id,nonce,"https://rag.zkd.id.vn")
    client=TestClient(create_local_compute_app(runtime)); headers={"Origin":"https://rag.zkd.id.vn","X-ZKD-Local-Grant":grant,"X-ZKD-Browser-Nonce":nonce}
    try:
        accepted=client.post("/v1/sessions",headers=headers); assert accepted.status_code==200 and accepted.json()["allowed_operations"]==sorted(claims["operations"])
        assert client.post("/v1/sessions",headers=headers).status_code==409
        assert grant.encode() not in runtime.settings.catalog_path.read_bytes() and accepted.json()["session_key"].encode() not in runtime.settings.catalog_path.read_bytes()
        bad=dict(headers); bad["X-ZKD-Browser-Nonce"]="wrong"; fresh,_=platform.issue_grant(user.id,device.id,"other","https://rag.zkd.id.vn"); bad["X-ZKD-Local-Grant"]=fresh
        assert client.post("/v1/sessions",headers=bad).status_code==401
        platform.revoke(user.id,device.id); runtime.control_channel.next_attempt_at=0; runtime.control_channel.tick()
        assert runtime.state==RuntimeState.REVOKED and not runtime.sessions._sessions
        assert client.post("/v1/sessions",headers=headers).status_code==503
    finally: runtime.shutdown()


def test_platform_session_authenticates_raw_binary_enforces_operation_and_revocation(tmp_path, platform_db):
    from fastapi.testclient import TestClient

    db, user = platform_db
    runtime, _, platform, device, _ = paired_runtime(tmp_path, db, user)
    signing = Ed25519PrivateKey.generate()
    platform.grant_key = base64.b64encode(signing.private_bytes_raw()).decode()
    public = base64.b64encode(signing.public_key().public_bytes_raw()).decode()
    runtime.control_channel.tick()
    runtime.grant_verifier = PlatformGrantVerifier(runtime, PlatformGrantVerificationKeyProvider(public))
    origin = "https://rag.zkd.id.vn"
    grant, _ = platform.issue_grant(user.id, device.id, "bound-browser-nonce", origin)
    client = TestClient(create_local_compute_app(runtime))

    def signed_headers(session: dict, method: str, path: str, body: bytes, *, nonce: str | None = None):
        timestamp = str(int(time.time()))
        nonce = nonce or str(uuid.uuid4())
        return {
            "Origin": origin,
            "X-ZKD-Local-Session": session["local_session_id"],
            "X-ZKD-Timestamp": timestamp,
            "X-ZKD-Nonce": nonce,
            "X-ZKD-MAC": request_mac(session["session_key"], method, path, timestamp, nonce, body),
            "X-ZKD-Protocol-Version": runtime.settings.protocol_version,
        }

    try:
        session_response = client.post(
            "/v1/sessions",
            headers={"Origin": origin, "X-ZKD-Local-Grant": grant, "X-ZKD-Browser-Nonce": "bound-browser-nonce"},
        )
        assert session_response.status_code == 200
        session = session_response.json()
        body = b"raw-binary-proof"
        headers = signed_headers(session, "POST", "/v1/probe/binary", body)
        assert client.post("/v1/probe/binary", content=body, headers=headers).status_code == 200
        assert client.post("/v1/probe/binary", content=body, headers=headers).status_code == 409

        document_id = str(uuid.uuid4())
        rejected_source = client.put(
            f"/v1/documents/{document_id}/source",
            content=b"not-a-pdf",
            headers={
                "Origin": origin,
                "X-ZKD-Local-Session": session["local_session_id"],
                "X-ZKD-Protocol-Version": runtime.settings.protocol_version,
            },
        )
        assert rejected_source.status_code == 401
        assert not (runtime.settings.documents_path / document_id).exists()

        source_body = b"not-a-pdf"
        source_headers = signed_headers(
            session,
            "PUT",
            f"/v1/documents/{document_id}/source",
            source_body,
        )
        authenticated_source = client.put(
            f"/v1/documents/{document_id}/source",
            content=source_body,
            headers=source_headers,
        )
        assert authenticated_source.status_code == 400
        assert authenticated_source.json()["error"]["code"] == "INVALID_PDF"

        tampered = signed_headers(session, "POST", "/v1/probe/binary", body)
        tampered["X-ZKD-MAC"] = "0" * 64
        assert client.post("/v1/probe/binary", content=body, headers=tampered).status_code == 401

        local_session = runtime.sessions._sessions[session["local_session_id"]]
        local_session.allowed_operations = frozenset({"retrieval"})
        query_path = "/v1/queries"
        query_body = json.dumps({"query_text": "doanh nghiệp"}).encode()
        assert client.post(
            query_path,
            content=query_body,
            headers={**signed_headers(session, "POST", query_path, query_body), "Content-Type": "application/json"},
        ).status_code == 200
        answer_path = "/v1/answers"
        answer_body = json.dumps({"query_text": "doanh nghiệp"}).encode()
        assert client.post(
            answer_path,
            content=answer_body,
            headers={**signed_headers(session, "POST", answer_path, answer_body), "Content-Type": "application/json"},
        ).status_code == 403
        forbidden = signed_headers(session, "POST", "/v1/probe/binary", body)
        assert client.post("/v1/probe/binary", content=body, headers=forbidden).status_code == 403

        local_session.allowed_operations = frozenset({"documents"})
        altered_pairing = runtime.catalog.get_paired_device_state()
        assert altered_pairing is not None
        altered_pairing["credential_epoch"] = device.credential_epoch + 1
        runtime.catalog.set_paired_device_state(altered_pairing)
        binding_invalid = signed_headers(session, "POST", "/v1/probe/binary", body)
        assert client.post("/v1/probe/binary", content=body, headers=binding_invalid).status_code == 401

        runtime.revoke()
        revoked = signed_headers(session, "POST", "/v1/probe/binary", body)
        revoked_response = client.post("/v1/probe/binary", content=body, headers=revoked)
        assert revoked_response.status_code == 503
        assert revoked_response.json()["error"]["code"] == "NOT_PAIRED"
    finally:
        runtime.shutdown()


def test_authenticated_local_protocol_e2e_survives_platform_outage_then_revocation(tmp_path, platform_db):
    from fastapi.testclient import TestClient

    db, user = platform_db
    runtime, transport, platform, device, _ = paired_runtime(tmp_path, db, user)
    signing = Ed25519PrivateKey.generate()
    platform.grant_key = base64.b64encode(signing.private_bytes_raw()).decode()
    public = base64.b64encode(signing.public_key().public_bytes_raw()).decode()
    runtime.control_channel.tick()
    runtime.grant_verifier = PlatformGrantVerifier(runtime, PlatformGrantVerificationKeyProvider(public))
    origin = "https://rag.zkd.id.vn"
    browser_nonce = "e2e-browser-nonce"
    grant, _ = platform.issue_grant(user.id, device.id, browser_nonce, origin)
    client = TestClient(create_local_compute_app(runtime))

    def signed_headers(session: dict, method: str, path: str, body: bytes) -> dict[str, str]:
        timestamp = str(int(time.time()))
        nonce = str(uuid.uuid4())
        return {
            "Origin": origin,
            "X-ZKD-Local-Session": session["local_session_id"],
            "X-ZKD-Timestamp": timestamp,
            "X-ZKD-Nonce": nonce,
            "X-ZKD-MAC": request_mac(session["session_key"], method, path, timestamp, nonce, body),
            "X-ZKD-Protocol-Version": runtime.settings.protocol_version,
        }

    try:
        session_response = client.post(
            "/v1/sessions",
            headers={"Origin": origin, "X-ZKD-Local-Grant": grant, "X-ZKD-Browser-Nonce": browser_nonce},
        )
        assert session_response.status_code == 200
        session = session_response.json()
        document_id = str(uuid.uuid4())
        source = _pdf_bytes(
            "NGHỊ ĐỊNH\nSố: 01/2026\nĐiều 1. Phạm vi điều chỉnh.\n"
            "Quy định này áp dụng cho doanh nghiệp."
        )
        source_path = f"/v1/documents/{document_id}/source"
        source_response = client.put(
            source_path,
            content=source,
            headers={
                **signed_headers(session, "PUT", source_path, source),
                "Content-Type": "application/pdf",
                "X-ZKD-Filename": "legal.pdf",
            },
        )
        assert source_response.status_code == 200, source_response.text

        prepare_path = f"/v1/documents/{document_id}/prepare"
        prepare_response = client.post(
            prepare_path,
            content=b"",
            headers=signed_headers(session, "POST", prepare_path, b""),
        )
        assert prepare_response.status_code == 200, prepare_response.text

        index_path = f"/v1/documents/{document_id}/index"
        index_response = client.post(
            index_path,
            content=b"",
            headers=signed_headers(session, "POST", index_path, b""),
        )
        assert index_response.status_code == 200, index_response.text

        query_path = "/v1/queries"
        query_body = json.dumps({"query_text": "doanh nghiệp áp dụng", "document_ids": [document_id]}).encode()
        query_response = client.post(
            query_path,
            content=query_body,
            headers={**signed_headers(session, "POST", query_path, query_body), "Content-Type": "application/json"},
        )
        assert query_response.status_code == 200, query_response.text
        assert query_response.json()["results"]

        state_path = f"/v1/documents/{document_id}"
        state_response = client.get(state_path, headers=signed_headers(session, "GET", state_path, b""))
        assert state_response.status_code == 200

        transport.available = False
        offline_response = client.post(
            query_path,
            content=query_body,
            headers={**signed_headers(session, "POST", query_path, query_body), "Content-Type": "application/json"},
        )
        assert offline_response.status_code == 200, offline_response.text

        transport.available = True
        platform.revoke(user.id, device.id)
        runtime.control_channel.next_attempt_at = 0
        runtime.control_channel.tick()
        revoked_response = client.post(
            query_path,
            content=query_body,
            headers={**signed_headers(session, "POST", query_path, query_body), "Content-Type": "application/json"},
        )
        assert revoked_response.status_code == 503
        assert revoked_response.json()["error"]["code"] == "NOT_PAIRED"
    finally:
        runtime.shutdown()
