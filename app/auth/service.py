import hashlib
import secrets
import uuid
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.passwords import dummy_verify, hash_password, verify_password
from app.auth.principal import Principal
from app.core.config import settings
from app.models.auth import (
    AccountDeletionDocumentRef,
    AccountDeletionJob,
    AccountDeletionState,
    AuthSession,
    DocumentAccessGrant,
    User,
    UserRole,
    UserStatus,
    utcnow,
)


INVALID_CREDENTIALS = "Invalid credentials."


class AuthenticationError(Exception):
    pass


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def provision_user(self, email: str, password: str, role: UserRole, must_change_password: bool = True) -> User:
        normalized = normalize_email(email)
        user = User(
            email=email.strip(), normalized_email=normalized, password_hash=hash_password(password),
            role=role.value, status=UserStatus.ACTIVE.value, must_change_password=must_change_password,
            created_at=utcnow(), updated_at=utcnow(),
        )
        self.db.add(user)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ValueError("A user with this email already exists")
        self.db.refresh(user)
        return user

    def login(self, email: str, password: str) -> tuple[User, AuthSession, str]:
        user = self.db.scalar(select(User).where(User.normalized_email == normalize_email(email)))
        if user is None:
            dummy_verify(password)
            raise AuthenticationError(INVALID_CREDENTIALS)
        valid = verify_password(user.password_hash, password)
        if not valid or user.status != UserStatus.ACTIVE.value:
            raise AuthenticationError(INVALID_CREDENTIALS)
        raw = secrets.token_urlsafe(32)
        now = utcnow()
        session = AuthSession(
            user_id=user.id, token_hash=token_hash(raw), created_at=now,
            expires_at=now + timedelta(seconds=settings.AUTH_SESSION_TTL_SECONDS),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return user, session, raw

    def resolve(self, raw_token: str | None) -> tuple[Principal, User] | None:
        if not raw_token:
            return None
        now = utcnow()
        row = self.db.execute(
            select(AuthSession, User)
            .join(User, User.id == AuthSession.user_id)
            .where(
                AuthSession.token_hash == token_hash(raw_token),
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
                User.status == UserStatus.ACTIVE.value,
            )
        ).one_or_none()
        if row is None:
            return None
        session, user = row
        return Principal(user.id, user.role, session.id), user

    def logout(self, raw_token: str | None) -> None:
        if raw_token:
            self.db.execute(
                update(AuthSession)
                .where(AuthSession.token_hash == token_hash(raw_token), AuthSession.revoked_at.is_(None))
                .values(revoked_at=utcnow())
            )
            self.db.commit()

    def change_password(self, principal: Principal, current_password: str, new_password: str) -> None:
        user = self.db.scalar(select(User).where(User.id == principal.user_id).with_for_update())
        if user is None or not verify_password(user.password_hash, current_password):
            raise AuthenticationError(INVALID_CREDENTIALS)
        now = utcnow()
        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        user.password_changed_at = now
        user.updated_at = now
        self.db.execute(update(AuthSession).where(AuthSession.user_id == user.id).values(revoked_at=now))
        self.db.commit()

    def request_account_deletion(self, principal: Principal, password: str) -> AccountDeletionJob:
        user = self.db.scalar(select(User).where(User.id == principal.user_id).with_for_update())
        if user is None or user.status != UserStatus.ACTIVE.value or not verify_password(user.password_hash, password):
            self.db.rollback()
            raise AuthenticationError(INVALID_CREDENTIALS)
        existing = self.db.scalar(
            select(AccountDeletionJob).where(
                AccountDeletionJob.subject_user_id == user.id,
                AccountDeletionJob.state.in_(("PENDING", "QUEUED", "RUNNING", "FAILED")),
            )
        )
        if existing:
            self.db.rollback()
            return existing
        job = AccountDeletionJob(
            subject_user_id=user.id, state=AccountDeletionState.PENDING.value,
            created_at=utcnow(), attempt_count=0,
        )
        self.db.add(job)
        self.db.flush()
        document_ids = self.db.scalars(
            select(DocumentAccessGrant.document_id).where(DocumentAccessGrant.user_id == user.id)
        ).all()
        self.db.add_all([
            AccountDeletionDocumentRef(job_id=job.id, document_id=document_id, state="PENDING")
            for document_id in document_ids
        ])
        user.status = UserStatus.DELETING.value
        user.updated_at = utcnow()
        self.db.execute(update(AuthSession).where(AuthSession.user_id == user.id).values(revoked_at=utcnow()))
        self.db.commit()
        self.db.refresh(job)
        return job
