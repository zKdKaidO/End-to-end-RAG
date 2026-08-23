import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TurnState(str, enum.Enum):
    PENDING = "PENDING"
    STREAMING = "STREAMING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class MessageRole(str, enum.Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


class DeliveryState(str, enum.Enum):
    COMMITTED = "COMMITTED"
    STREAMING = "STREAMING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(Text, nullable=False, default="New conversation")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    turns = relationship("ChatTurn", cascade="all, delete-orphan", passive_deletes=True)
    messages = relationship("ChatMessage", cascade="all, delete-orphan", passive_deletes=True)
    user = relationship("User", overlaps="chat_sessions")


class ChatTurn(Base):
    __tablename__ = "chat_turns"
    __table_args__ = (
        UniqueConstraint("session_id", "client_turn_id", name="uq_chat_turn_session_client"),
        CheckConstraint(
            "state IN ('PENDING','STREAMING','COMPLETED','FAILED','CANCELLED')",
            name="ck_chat_turn_state",
        ),
        CheckConstraint(
            "state <> 'COMPLETED' OR completed_at IS NOT NULL",
            name="ck_chat_turn_completed_at",
        ),
        Index(
            "uq_chat_turn_one_active_per_session",
            "session_id",
            unique=True,
            postgresql_where=text("state IN ('PENDING', 'STREAMING')"),
        ),
        Index("ix_chat_turn_session_created", "session_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    client_turn_id = Column(UUID(as_uuid=True), nullable=False)
    request_hash = Column(String(64), nullable=False)
    state = Column(String(24), nullable=False, default=TurnState.PENDING.value)
    document_scope_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    failure_code = Column(Text, nullable=True)
    failure_detail_safe = Column(Text, nullable=True)

    session = relationship("ChatSession", overlaps="turns")
    messages = relationship("ChatMessage", cascade="all, delete-orphan", passive_deletes=True)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence_no", name="uq_chat_message_session_sequence"),
        CheckConstraint("role IN ('USER','ASSISTANT')", name="ck_chat_message_role"),
        CheckConstraint(
            "delivery_state IN ('COMMITTED','STREAMING','COMPLETED','FAILED','CANCELLED')",
            name="ck_chat_message_delivery_state",
        ),
        CheckConstraint(
            "answer_status IS NULL OR answer_status IN ('ANSWERABLE','INSUFFICIENT_EVIDENCE')",
            name="ck_chat_message_answer_status",
        ),
        CheckConstraint(
            "delivery_state <> 'COMPLETED' OR finalized_at IS NOT NULL",
            name="ck_chat_message_completed_finalized",
        ),
        CheckConstraint(
            "delivery_state NOT IN ('FAILED','CANCELLED') OR answer_status IS NULL",
            name="ck_chat_message_terminal_answer_status",
        ),
        Index("ix_chat_message_session_sequence", "session_id", "sequence_no"),
        Index("ix_chat_message_turn", "turn_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    turn_id = Column(UUID(as_uuid=True), ForeignKey("chat_turns.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(16), nullable=False)
    sequence_no = Column(BigInteger, nullable=False)
    content = Column(Text, nullable=False, default="")
    delivery_state = Column(String(24), nullable=False)
    answer_status = Column(String(32), nullable=True)
    model_id = Column(Text, nullable=True)
    prompt_version = Column(Text, nullable=True)
    prompt_hash = Column(String(64), nullable=True)
    index_version = Column(Text, nullable=True)
    context_fingerprint = Column(String(64), nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    generation_latency_ms = Column(Integer, nullable=True)
    generation_metadata_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    finalized_at = Column(DateTime(timezone=True), nullable=True)

    session = relationship("ChatSession", overlaps="messages")
    turn = relationship("ChatTurn", overlaps="messages")
    citation_snapshots = relationship(
        "MessageCitationSnapshot", cascade="all, delete-orphan", passive_deletes=True, order_by="MessageCitationSnapshot.citation_order"
    )


class MessageCitationSnapshot(Base):
    __tablename__ = "message_citation_snapshots"
    __table_args__ = (
        UniqueConstraint("message_id", "citation_label", name="uq_chat_citation_message_label"),
        UniqueConstraint("message_id", "citation_order", name="uq_chat_citation_message_order"),
        CheckConstraint("citation_order > 0", name="ck_chat_citation_order_positive"),
        CheckConstraint("snapshot_version > 0", name="ck_chat_citation_snapshot_version_positive"),
        Index("ix_chat_citation_message", "message_id", "citation_order"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False)
    citation_label = Column(Text, nullable=False)
    citation_order = Column(Integer, nullable=False)
    original_document_id = Column(UUID(as_uuid=True), nullable=True)
    original_chunk_id = Column(UUID(as_uuid=True), nullable=True)
    original_legal_unit_id = Column(UUID(as_uuid=True), nullable=True)
    document_title = Column(Text, nullable=True)
    document_filename = Column(Text, nullable=True)
    document_sha256 = Column(String(64), nullable=True)
    chunk_content_sha256 = Column(String(64), nullable=False)
    page_start = Column(Integer, nullable=True)
    page_end = Column(Integer, nullable=True)
    article = Column(Text, nullable=True)
    clause = Column(Text, nullable=True)
    point = Column(Text, nullable=True)
    evidence_text = Column(Text, nullable=False)
    metadata_json = Column(JSONB, nullable=False, default=dict)
    provenance_json = Column(JSONB, nullable=False, default=dict)
    snapshot_version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    message = relationship("ChatMessage", overlaps="citation_snapshots")
