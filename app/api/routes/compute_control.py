"""Authenticated platform control APIs; they never accept document/RAG content."""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_authenticated_user
from app.auth.principal import Principal
from app.compute_control import ComputeControlError, ComputeControlService
from app.core.config import settings
from app.db.database import get_db
from app.models.compute_control import ComputeDevice, LocalDocumentManifest

router=APIRouter(prefix="/api/v1/compute",tags=["compute-control"])

def service(db: Session) -> ComputeControlService:
    return ComputeControlService(db,grant_key=settings.COMPUTE_GRANT_SIGNING_KEY,pairing_ttl_seconds=settings.COMPUTE_PAIRING_TTL_SECONDS,grant_ttl_seconds=settings.COMPUTE_LOCAL_SESSION_GRANT_TTL_SECONDS,auth_window_seconds=settings.COMPUTE_DEVICE_AUTH_WINDOW_SECONDS,presence_ttl_seconds=settings.COMPUTE_PRESENCE_FRESHNESS_SECONDS)
def fail(exc: ComputeControlError): raise HTTPException(400 if exc.code.startswith(("PAIRING_","MANIFEST_","FORBIDDEN_")) else 403 if exc.code in {"DEVICE_AUTH_INVALID","DEVICE_REPLAY_DETECTED","DEVICE_REVOKED"} else 404 if exc.code=="DEVICE_NOT_FOUND" else 503,detail={"error_code":exc.code,"message":exc.message})

@router.post("/pairing-challenges",status_code=201)
def create_pairing(principal:Principal=Depends(require_authenticated_user),db:Session=Depends(get_db)):
    item,token,code=service(db).create_pairing(principal.user_id)
    return {"pairing_request_id":str(item.id),"pairing_token":token,"confirmation_code":code,"expires_at":item.expires_at}
@router.post("/pairing-challenges/{challenge_id}/confirm")
def confirm_pairing(challenge_id:UUID,payload:dict[str,Any],principal:Principal=Depends(require_authenticated_user),db:Session=Depends(get_db)):
    try: device=service(db).confirm_pairing(principal.user_id,challenge_id,str(payload.get("confirmation_code","")))
    except ComputeControlError as exc: fail(exc)
    return {"device_id":str(device.id),"state":"CONFIRMED"}
@router.get("/devices")
def list_devices(principal:Principal=Depends(require_authenticated_user),db:Session=Depends(get_db)):
    control=service(db); return {"devices":[control.device_state(principal.user_id,item) for item in db.scalars(select(ComputeDevice).where(ComputeDevice.owner_user_id==principal.user_id)).all()]}
@router.post("/devices/{device_id}/revoke")
def revoke(device_id:UUID,principal:Principal=Depends(require_authenticated_user),db:Session=Depends(get_db)):
    try: item=service(db).revoke(principal.user_id,device_id)
    except ComputeControlError as exc: fail(exc)
    return {"device_id":str(item.id),"state":"REVOKED","credential_epoch":item.credential_epoch}
@router.post("/devices/{device_id}/local-session-grants")
def issue_grant(device_id:UUID,payload:dict[str,Any],request:Request,principal:Principal=Depends(require_authenticated_user),db:Session=Depends(get_db)):
    origin=request.headers.get("origin", "")
    trusted={value.strip() for value in settings.AUTH_TRUSTED_ORIGINS.split(",") if value.strip()}
    if origin not in trusted:
        raise HTTPException(403,detail={"error_code":"UNTRUSTED_ORIGIN","message":"Local session grants require a trusted browser origin."})
    try: grant,claims=service(db).issue_grant(principal.user_id,device_id,str(payload.get("browser_nonce","")),request.headers.get("origin", ""))
    except ComputeControlError as exc: fail(exc)
    return {"local_access_grant":grant,"expires_at":claims["exp"],"device_id":claims["device_id"],"endpoint_generation":claims["endpoint_generation"]}
@router.get("/local-manifests")
def manifests(principal:Principal=Depends(require_authenticated_user),db:Session=Depends(get_db)):
    control=service(db)
    return {"manifests":[control.manifest_read_model(principal.user_id, x) for x in db.scalars(select(LocalDocumentManifest).where(LocalDocumentManifest.owner_user_id==principal.user_id)).all()]}

async def device(request:Request,db:Session):
    body=await request.body(); h=request.headers
    try: return service(db).authenticate_device(device_id=UUID(h.get("X-ZKD-Device-ID","")),epoch=int(h.get("X-ZKD-Credential-Epoch","")),timestamp=h.get("X-ZKD-Timestamp",""),nonce=h.get("X-ZKD-Nonce",""),signature_b64=h.get("X-ZKD-Signature",""),method=request.method,path=request.url.path,body=body)
    except (ValueError,ComputeControlError) as exc: fail(exc if isinstance(exc,ComputeControlError) else ComputeControlError("DEVICE_AUTH_INVALID"))
@router.post("/control/pairing-challenges/{challenge_id}/complete")
def complete_pairing(challenge_id:UUID,payload:dict[str,Any],db:Session=Depends(get_db)):
    try: d=service(db).complete_pairing(challenge_id,str(payload.get("pairing_token","")),str(payload.get("public_key","")),str(payload.get("signature","")),str(payload.get("protocol_version","")),str(payload.get("runtime_version","")),payload.get("friendly_label"))
    except ComputeControlError as exc: fail(exc)
    return {"device_id":str(d.id),"state":"AWAITING_CONFIRMATION"}
@router.post("/control/presence")
async def presence(request:Request,db:Session=Depends(get_db)):
    d=await device(request,db)
    try: p=service(db).publish_presence(d,await request.json())
    except ComputeControlError as exc: fail(exc)
    return {"device_id":str(d.id),"last_seen_at":p.last_seen_at}
@router.post("/control/manifests")
async def manifest(request:Request,db:Session=Depends(get_db)):
    d=await device(request,db)
    try: m=service(db).upsert_manifest(d,await request.json())
    except ComputeControlError as exc: fail(exc)
    return {"document_id":str(m.document_id),"device_id":str(d.id),"updated_at":m.updated_at}
