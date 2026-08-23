import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin
from app.auth.principal import Principal
from app.auth.schemas import ProvisionUserRequest, SetUserStatusRequest
from app.auth.service import AuthService
from app.db.database import get_db
from app.models.auth import AccountDeletionJob, AccountDeletionState, AuthSession, User, UserRole, UserStatus, utcnow
from app.queue.rq_client import rq_client


router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/users", status_code=201)
def provision_user(
    payload: ProvisionUserRequest,
    _principal: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        role = UserRole(payload.role)
        user = AuthService(db).provision_user(
            payload.email, payload.temporary_password, role, must_change_password=True,
        )
    except ValueError as exc:
        raise HTTPException(400, detail={"error_code": "INVALID_USER", "message": str(exc)}) from exc
    return {"id": str(user.id), "email": user.email, "role": user.role, "status": user.status, "must_change_password": True}


@router.patch("/users/{user_id}/status")
def set_user_status(
    user_id: uuid.UUID,
    payload: SetUserStatusRequest,
    principal: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if user_id == principal.user_id:
        raise HTTPException(400, detail={"error_code": "SELF_STATUS_CHANGE_REJECTED", "message": "Use the account lifecycle endpoint."})
    if payload.status not in {UserStatus.ACTIVE.value, UserStatus.DISABLED.value}:
        raise HTTPException(400, detail={"error_code": "INVALID_STATUS", "message": "Status must be ACTIVE or DISABLED."})
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None or user.status == UserStatus.DELETING.value:
        raise HTTPException(404, detail={"error_code": "RESOURCE_NOT_FOUND", "message": "Resource not found."})
    user.status = payload.status
    user.updated_at = utcnow()
    if payload.status == UserStatus.DISABLED.value:
        db.execute(update(AuthSession).where(AuthSession.user_id == user.id).values(revoked_at=utcnow()))
    db.commit()
    return {"id": str(user.id), "status": user.status}


@router.post("/account-deletions/{job_id}/retry", status_code=202)
def retry_account_deletion(
    job_id: uuid.UUID,
    request: Request,
    _principal: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
):
    job = db.scalar(select(AccountDeletionJob).where(AccountDeletionJob.id == job_id).with_for_update())
    if job is None:
        raise HTTPException(404, detail={"error_code": "RESOURCE_NOT_FOUND", "message": "Resource not found."})
    if job.state == AccountDeletionState.COMPLETED.value:
        return {"job_id": str(job.id), "state": job.state}
    try:
        rq_client.enqueue_account_deletion_job(str(job.id), request.state.request_id)
        db.execute(
            update(AccountDeletionJob)
            .where(
                AccountDeletionJob.id == job.id,
                AccountDeletionJob.state.in_((
                    AccountDeletionState.PENDING.value,
                    AccountDeletionState.FAILED.value,
                )),
            )
            .values(state=AccountDeletionState.QUEUED.value)
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(503, detail={"error_code": "QUEUE_UNAVAILABLE", "message": "Cleanup retry remains durable."}) from exc
    state = db.scalar(select(AccountDeletionJob.state).where(AccountDeletionJob.id == job.id))
    return {"job_id": str(job.id), "state": state}
