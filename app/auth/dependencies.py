from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.principal import Principal
from app.auth.service import AuthService
from app.core.config import settings
from app.db.database import get_db
from app.models.auth import UserRole


def get_current_principal(
    raw_token: str | None = Cookie(default=None, alias=settings.AUTH_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> Principal:
    resolved = AuthService(db).resolve(raw_token)
    if resolved is None:
        raise HTTPException(401, detail={"error_code": "AUTHENTICATION_REQUIRED", "message": "Authentication required."})
    return resolved[0]


def require_authenticated_user(principal: Principal = Depends(get_current_principal)) -> Principal:
    return principal


def require_admin(principal: Principal = Depends(get_current_principal)) -> Principal:
    if principal.role != UserRole.ADMIN.value:
        raise HTTPException(403, detail={"error_code": "FORBIDDEN", "message": "Administrator access required."})
    return principal
