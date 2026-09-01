"""Isolated P2C.5B.1 Compute → Platform control-channel acceptance tests."""
from __future__ import annotations

import base64
import json
import uuid

import pytest
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
from app.models.auth import User, UserRole, UserStatus
from app.models.compute_control import ComputeDevice, ComputeLocalSessionGrant, ComputePairingChallenge, ComputePresence, ComputeReplayNonce, LocalDocumentManifest


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


def test_production_credential_store_fails_closed(tmp_path):
    runtime=LocalComputeRuntime(LocalComputeSettings(data_root=tmp_path/"Compute"),credential_store=UnavailableDeviceCredentialStore()); runtime.start()
    try:
        with pytest.raises(LocalComputeError) as unavailable: runtime.credential_store.load_private_key()
        assert unavailable.value.code==LocalComputeErrorCode.CREDENTIAL_STORE_UNAVAILABLE
    finally: runtime.shutdown()
