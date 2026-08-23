import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    DELETING = "DELETING"


class AccountDeletionState(str, enum.Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AccountDeletionDocumentState(str, enum.Enum):
    PENDING = "PENDING"
    RETAINED_REFERENCED = "RETAINED_REFERENCED"
    DELETED = "DELETED"
    FAILED = "FAILED"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('USER','ADMIN')", name="ck_user_role"),
        CheckConstraint("status IN ('ACTIVE','DISABLED','DELETING')", name="ck_user_status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(Text, nullable=False)
    normalized_email = Column(Text, nullable=False, unique=True)
    password_hash = Column(Text, nullable=False)
    role = Column(String(16), nullable=False, default=UserRole.USER.value)
    status = Column(String(16), nullable=False, default=UserStatus.ACTIVE.value)
    must_change_password = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    password_changed_at = Column(DateTime(timezone=True), nullable=True)

    auth_sessions = relationship("AuthSession", cascade="all, delete-orphan", passive_deletes=True)
    chat_sessions = relationship("ChatSession", passive_deletes=True)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (Index("ix_auth_session_user_active", "user_id", "expires_at", "revoked_at"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", overlaps="auth_sessions")


class DocumentAccessGrant(Base):
    __tablename__ = "document_access_grants"
    __table_args__ = (
        Index("ix_document_access_user_document", "user_id", "document_id"),
        Index("ix_document_access_document_user", "document_id", "user_id"),
    )

    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class GlobalDocumentAccess(Base):
    __tablename__ = "global_document_access"

    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    granted_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class AccountDeletionJob(Base):
    __tablename__ = "account_deletion_jobs"
    __table_args__ = (
        CheckConstraint("state IN ('PENDING','QUEUED','RUNNING','COMPLETED','FAILED')", name="ck_account_deletion_state"),
        Index(
            "uq_account_deletion_one_active",
            "subject_user_id",
            unique=True,
            postgresql_where=text("state IN ('PENDING','QUEUED','RUNNING','FAILED')"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_user_id = Column(UUID(as_uuid=True), nullable=False)
    state = Column(String(16), nullable=False, default=AccountDeletionState.PENDING.value)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    failure_code = Column(Text, nullable=True)
    failure_detail_safe = Column(Text, nullable=True)

    document_refs = relationship("AccountDeletionDocumentRef", cascade="all, delete-orphan", passive_deletes=True)


class AccountDeletionDocumentRef(Base):
    __tablename__ = "account_deletion_document_refs"
    __table_args__ = (
        CheckConstraint(
            "state IN ('PENDING','RETAINED_REFERENCED','DELETED','FAILED')",
            name="ck_account_deletion_document_state",
        ),
        UniqueConstraint("job_id", "document_id", name="uq_account_deletion_document"),
        Index("ix_account_deletion_document_state", "job_id", "state"),
    )

    job_id = Column(UUID(as_uuid=True), ForeignKey("account_deletion_jobs.id", ondelete="CASCADE"), primary_key=True)
    document_id = Column(UUID(as_uuid=True), primary_key=True)
    state = Column(String(24), nullable=False, default=AccountDeletionDocumentState.PENDING.value)
    failure_code = Column(Text, nullable=True)
    failure_detail_safe = Column(Text, nullable=True)
