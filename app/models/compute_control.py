"""Metadata-only platform control-plane records for paired ZKD Compute devices."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ComputeDevice(Base):
    __tablename__ = "compute_devices"
    __table_args__ = (Index("ix_compute_device_owner", "owner_user_id", "revoked_at"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    public_key = Column(String(128), nullable=False, unique=True)
    friendly_label = Column(String(120), nullable=True)
    credential_epoch = Column(Integer, nullable=False, default=1)
    protocol_version = Column(String(64), nullable=False)
    runtime_version = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    revoked_at = Column(DateTime(timezone=True), nullable=True)


class ComputePairingChallenge(Base):
    __tablename__ = "compute_pairing_challenges"
    __table_args__ = (CheckConstraint("state IN ('PENDING','AWAITING_CONFIRMATION','CONFIRMED','CONSUMED','EXPIRED','CANCELLED')", name="ck_compute_pairing_state"), Index("ix_compute_pairing_owner_expiry", "owner_user_id", "expires_at"))
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)
    confirmation_code_hash = Column(String(64), nullable=False)
    state = Column(String(32), nullable=False, default="PENDING")
    pending_device_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)


class ComputePresence(Base):
    __tablename__ = "compute_presence"
    device_id = Column(UUID(as_uuid=True), ForeignKey("compute_devices.id", ondelete="CASCADE"), primary_key=True)
    state = Column(String(32), nullable=False)
    protocol_version = Column(String(64), nullable=False)
    runtime_version = Column(String(64), nullable=False)
    endpoint_generation = Column(String(128), nullable=False)
    endpoint_port = Column(Integer, nullable=True)
    capabilities_json = Column(JSONB, nullable=False, default=dict)
    provider_metadata_json = Column(JSONB, nullable=False, default=dict)
    last_seen_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class LocalDocumentManifest(Base):
    __tablename__ = "local_document_manifests"
    __table_args__ = (UniqueConstraint("owner_user_id", "device_id", "document_id", name="uq_local_manifest_owner_device_document"), Index("ix_local_manifest_owner_document", "owner_user_id", "document_id"))
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_id = Column(UUID(as_uuid=True), ForeignKey("compute_devices.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(UUID(as_uuid=True), nullable=False)
    filename = Column(String(255), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    preparation_state = Column(String(32), nullable=False)
    index_state = Column(String(32), nullable=False)
    chunk_count = Column(Integer, nullable=True)
    artifact_id = Column(UUID(as_uuid=True), nullable=True)
    artifact_version = Column(String(128), nullable=True)
    artifact_profile_fingerprint = Column(String(64), nullable=True)
    local_availability = Column(String(32), nullable=False)
    error_code = Column(String(96), nullable=True)
    error_message = Column(String(512), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class ComputeReplayNonce(Base):
    __tablename__ = "compute_replay_nonces"
    device_id = Column(UUID(as_uuid=True), ForeignKey("compute_devices.id", ondelete="CASCADE"), primary_key=True)
    nonce_hash = Column(String(64), primary_key=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)


class ComputeLocalSessionGrant(Base):
    __tablename__ = "compute_local_session_grants"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_id = Column(UUID(as_uuid=True), ForeignKey("compute_devices.id", ondelete="CASCADE"), nullable=False)
    credential_epoch = Column(Integer, nullable=False)
    endpoint_generation = Column(String(128), nullable=False)
    origin = Column(String(255), nullable=False)
    browser_nonce_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
