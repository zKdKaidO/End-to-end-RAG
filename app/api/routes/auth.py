from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth.dependencies import require_authenticated_user
from app.auth.principal import Principal
from app.auth.schemas import ChangePasswordRequest, DeleteAccountRequest, LoginRequest, UserResponse
from app.auth.service import AuthenticationError, AuthService
from app.core.config import settings
from app.db.database import get_db
from app.models.auth import AccountDeletionJob, AccountDeletionState, User
from app.queue.rq_client import rq_client
from app.security.rate_limits import SecurityControlUnavailable, login_rate_limiter
from app.deployment.tombstones import TombstoneStoreUnavailable, deletion_tombstone_store


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id), email=user.email, role=user.role, status=user.status,
        must_change_password=bool(user.must_change_password),
    )


@router.post("/login", response_model=UserResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    try:
        decision = login_rate_limiter.consume(request.client.host if request.client else "unknown", payload.email)
    except SecurityControlUnavailable as exc:
        raise HTTPException(503, detail={"error_code": "SECURITY_CONTROL_UNAVAILABLE", "message": "Authentication is temporarily unavailable."}) from exc
    if not decision.allowed:
        raise HTTPException(
            429,
            detail={"error_code": "LOGIN_RATE_LIMITED", "message": "Too many login attempts. Try again later."},
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )
    try:
        user, _session, raw_token = AuthService(db).login(payload.email, payload.password)
    except AuthenticationError as exc:
        raise HTTPException(401, detail={"error_code": "INVALID_CREDENTIALS", "message": str(exc)}) from exc
    response.set_cookie(
        settings.AUTH_COOKIE_NAME, raw_token, max_age=settings.AUTH_SESSION_TTL_SECONDS,
        httponly=True, secure=settings.AUTH_COOKIE_SECURE, samesite="lax", path="/",
    )
    return _user_response(user)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    request: Request,
    _principal: Principal = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
    AuthService(db).logout(request.cookies.get(settings.AUTH_COOKIE_NAME))
    response.delete_cookie(settings.AUTH_COOKIE_NAME, path="/", secure=settings.AUTH_COOKIE_SECURE, httponly=True, samesite="lax")


@router.get("/me", response_model=UserResponse)
def me(principal: Principal = Depends(require_authenticated_user), db: Session = Depends(get_db)):
    return _user_response(db.get(User, principal.user_id))


@router.post("/change-password", status_code=204)
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    principal: Principal = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
    try:
        AuthService(db).change_password(principal, payload.current_password, payload.new_password)
    except (AuthenticationError, ValueError) as exc:
        status = 401 if isinstance(exc, AuthenticationError) else 400
        raise HTTPException(status, detail={"error_code": "PASSWORD_CHANGE_REJECTED", "message": str(exc)}) from exc
    response.delete_cookie(settings.AUTH_COOKIE_NAME, path="/", secure=settings.AUTH_COOKIE_SECURE, httponly=True, samesite="lax")


@router.delete("/account", status_code=202)
def delete_account(
    payload: DeleteAccountRequest,
    request: Request,
    response: Response,
    principal: Principal = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
    try:
        job = AuthService(db).request_account_deletion(principal, payload.password)
    except AuthenticationError as exc:
        raise HTTPException(401, detail={"error_code": "INVALID_CREDENTIALS", "message": str(exc)}) from exc
    try:
        deletion_tombstone_store.record(str(job.subject_user_id), str(job.id), job.created_at)
    except TombstoneStoreUnavailable as exc:
        response.delete_cookie(settings.AUTH_COOKIE_NAME, path="/", secure=settings.AUTH_COOKIE_SECURE, httponly=True, samesite="lax")
        raise HTTPException(
            503,
            detail={"error_code": "DELETION_RECOVERY_CONTROL_UNAVAILABLE", "message": "Account deletion is pending durable recovery protection."},
        ) from exc

    queued = False
    try:
        rq_client.enqueue_account_deletion_job(str(job.id), request.state.request_id)
        # A fast worker may already own RUNNING/COMPLETED. Only advance the
        # durable state that this request originally committed.
        db.execute(
            update(AccountDeletionJob)
            .where(
                AccountDeletionJob.id == job.id,
                AccountDeletionJob.state == AccountDeletionState.PENDING.value,
            )
            .values(state=AccountDeletionState.QUEUED.value)
        )
        db.commit()
        queued = True
    except Exception:
        db.rollback()  # Durable PENDING intent remains for reconciliation.
    response.delete_cookie(settings.AUTH_COOKIE_NAME, path="/", secure=settings.AUTH_COOKIE_SECURE, httponly=True, samesite="lax")
    current_state = db.scalar(
        select(AccountDeletionJob.state).where(AccountDeletionJob.id == job.id)
    )
    return {"job_id": str(job.id), "state": current_state or ("QUEUED" if queued else "PENDING")}
