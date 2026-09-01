import base64, hashlib, json, time, uuid

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.auth.dependencies import require_authenticated_user
from app.auth.principal import Principal
from app.auth.passwords import hash_password
from app.compute_control import ComputeControlError, ComputeControlService
from app.db.database import SessionLocal
from app.main import app
from app.models.auth import User, UserRole, UserStatus
from app.models.compute_control import ComputeDevice, ComputeLocalSessionGrant, ComputePairingChallenge, ComputePresence, ComputeReplayNonce, LocalDocumentManifest


def keypair():
    private=Ed25519PrivateKey.generate(); public=base64.b64encode(private.public_key().public_bytes_raw()).decode(); return private,public
def grant_keypair():
    private=Ed25519PrivateKey.generate(); return base64.b64encode(private.private_bytes_raw()).decode(),base64.b64encode(private.public_key().public_bytes_raw()).decode()
def sign(private, method,path,epoch,nonce,body):
    value="|".join((method,path,str(epoch),str(int(time.time())),nonce,hashlib.sha256(body).hexdigest())).encode(); return base64.b64encode(private.sign(value)).decode(),value
@pytest.fixture
def db():
    session=SessionLocal(); users=[]
    yield session,users
    ids=[u.id for u in users];
    if ids:
        session.execute(delete(ComputeLocalSessionGrant).where(ComputeLocalSessionGrant.owner_user_id.in_(ids))); session.execute(delete(LocalDocumentManifest).where(LocalDocumentManifest.owner_user_id.in_(ids))); session.execute(delete(ComputePresence).where(ComputePresence.device_id.in_(session.query(ComputeDevice.id).filter(ComputeDevice.owner_user_id.in_(ids))))); session.execute(delete(ComputeReplayNonce).where(ComputeReplayNonce.device_id.in_(session.query(ComputeDevice.id).filter(ComputeDevice.owner_user_id.in_(ids))))); session.execute(delete(ComputePairingChallenge).where(ComputePairingChallenge.owner_user_id.in_(ids))); session.execute(delete(ComputeDevice).where(ComputeDevice.owner_user_id.in_(ids))); session.execute(delete(User).where(User.id.in_(ids))); session.commit()
    session.close()
def user(db, users):
    x=User(email=f"{uuid.uuid4()}@x.invalid",normalized_email=f"{uuid.uuid4()}@x.invalid",password_hash=hash_password("correct horse battery staple"),role=UserRole.USER.value,status=UserStatus.ACTIVE.value); db.add(x);db.commit();users.append(x);return x
def paired(control, owner):
    challenge,token,code=control.create_pairing(owner.id); private,public=keypair(); signature=base64.b64encode(private.sign(f"pairing|{challenge.id}|{token}".encode())).decode(); device=control.complete_pairing(challenge.id,token,public,signature,"zkd-compute-v1","0.1","test"); control.confirm_pairing(owner.id,challenge.id,code);return device,private
def auth(control,device,private,path,body):
    nonce=str(uuid.uuid4()); signature,canonical=sign(private,"POST",path,device.credential_epoch,nonce,body); timestamp=canonical.decode().split("|")[3];return control.authenticate_device(device_id=device.id,epoch=device.credential_epoch,timestamp=timestamp,nonce=nonce,signature_b64=signature,method="POST",path=path,body=body)

def test_pairing_proof_confirm_replay_presence_manifest_grant_and_privacy(db):
    session,users=db; alice=user(session,users); grant_private,grant_public=grant_keypair(); control=ComputeControlService(session,grant_key=grant_private)
    device,private=paired(control,alice)
    payload={"state":"READY","protocol_version":"zkd-compute-v1","runtime_version":"0.1","endpoint_generation":"eg-1","endpoint_port":43210,"capabilities":{"retrieval":"READY","generation":"READY"},"provider_metadata":{"local":"READY"}}
    raw=json.dumps(payload).encode(); assert auth(control,device,private,"/api/v1/compute/control/presence",raw).id==device.id; control.publish_presence(device,payload)
    manifest={"document_id":str(uuid.uuid4()),"filename":"only-name.pdf","size_bytes":12,"preparation_state":"READY","index_state":"READY","chunk_count":2,"artifact_id":str(uuid.uuid4()),"artifact_version":"v1","artifact_profile_fingerprint":"a"*64,"local_availability":"AVAILABLE"}; auth(control,device,private,"/api/v1/compute/control/manifests",json.dumps(manifest).encode()); control.upsert_manifest(device,manifest)
    state=control.device_state(alice.id,device); assert state["state"]=="READY" and state["endpoint_port"]==43210
    grant,claims=control.issue_grant(alice.id,device.id,"browser-nonce","https://rag.zkd.id.vn"); assert grant.count(".")==1 and claims["device_id"]==str(device.id)
    assert ComputeControlService.verify_grant_signature(grant,grant_public)==claims
    with pytest.raises(ComputeControlError): ComputeControlService.verify_grant_signature(grant+"x",grant_public)
    row=session.query(LocalDocumentManifest).one(); assert control.manifest_read_model(alice.id,row)["queryable"] is True and not any(hasattr(row,x) for x in ("pdf_bytes","page_text","chunk_text","embedding","prompt","context","answer"))
    with pytest.raises(ComputeControlError) as blocked: control.upsert_manifest(device,{**manifest,"prompt":"leak"})
    assert blocked.value.code=="FORBIDDEN_MANIFEST_CONTENT"
    nonce="replay"; signature,canonical=sign(private,"POST", "/x",device.credential_epoch,nonce,b"{}"); timestamp=canonical.decode().split("|")[3]; control.authenticate_device(device_id=device.id,epoch=device.credential_epoch,timestamp=timestamp,nonce=nonce,signature_b64=signature,method="POST",path="/x",body=b"{}")
    with pytest.raises(ComputeControlError): control.authenticate_device(device_id=device.id,epoch=device.credential_epoch,timestamp=timestamp,nonce=nonce,signature_b64=signature,method="POST",path="/x",body=b"{}")

def test_ownership_and_revocation_fail_closed(db):
    session,users=db; alice,bob=user(session,users),user(session,users); grant_private,_=grant_keypair(); control=ComputeControlService(session,grant_key=grant_private); device,private=paired(control,alice)
    with pytest.raises(ComputeControlError): control.device_state(bob.id,device)
    with pytest.raises(ComputeControlError): control.issue_grant(bob.id,device.id,"n","https://rag.zkd.id.vn")
    control.revoke(alice.id,device.id)
    with pytest.raises(ComputeControlError): auth(control,device,private,"/x",b"{}")

def test_expiry_protocol_and_presence_validation(db):
    session,users=db; alice=user(session,users); grant_private,_=grant_keypair(); control=ComputeControlService(session,grant_key=grant_private,pairing_ttl_seconds=0,auth_window_seconds=1,presence_ttl_seconds=0)
    challenge,token,_=control.create_pairing(alice.id); private,public=keypair(); signature=base64.b64encode(private.sign(f"pairing|{challenge.id}|{token}".encode())).decode()
    with pytest.raises(ComputeControlError) as expired: control.complete_pairing(challenge.id,token,public,signature,"zkd-compute-v1","0.1",None)
    assert expired.value.code=="PAIRING_EXPIRED"
    control=ComputeControlService(session,grant_key=grant_private); device,private=paired(control,alice)
    with pytest.raises(ComputeControlError) as protocol: control.publish_presence(device,{"state":"READY","protocol_version":"old","runtime_version":"0.1","endpoint_generation":"e","capabilities":{}})
    assert protocol.value.code=="PROTOCOL_VERSION_UNSUPPORTED"
    with pytest.raises(ComputeControlError): control.publish_presence(device,{"state":"READY","protocol_version":"zkd-compute-v1","runtime_version":"0.1","endpoint_generation":"e","capabilities":{},"provider_metadata":{"prompt":"leak"}})

def test_browser_and_device_authentication_boundaries_are_separate(db):
    session,users=db; alice=user(session,users); grant_private,_=grant_keypair(); control=ComputeControlService(session,grant_key=grant_private); device,private=paired(control,alice)
    payload={"state":"READY","protocol_version":"zkd-compute-v1","runtime_version":"0.1","endpoint_generation":"eg-api","endpoint_port":43111,"capabilities":{"retrieval":"READY"}}
    raw=json.dumps(payload,separators=(",", ":")).encode(); nonce=str(uuid.uuid4()); signature,canonical=sign(private,"POST","/api/v1/compute/control/presence",device.credential_epoch,nonce,raw); timestamp=canonical.decode().split("|")[3]
    headers={"X-ZKD-Device-ID":str(device.id),"X-ZKD-Credential-Epoch":str(device.credential_epoch),"X-ZKD-Timestamp":timestamp,"X-ZKD-Nonce":nonce,"X-ZKD-Signature":signature}
    app.dependency_overrides[require_authenticated_user]=lambda: Principal(user_id=alice.id,role="USER",auth_session_id=uuid.uuid4())
    try:
        client=TestClient(app)
        assert client.post("/api/v1/compute/control/presence",json=payload).status_code==403
        assert client.post("/api/v1/compute/control/presence",content=raw,headers=headers).status_code==200
        assert client.get("/api/v1/compute/devices").status_code==200
    finally:
        app.dependency_overrides.pop(require_authenticated_user,None)
