"""Add persistent product chat history.

Revision ID: chat_session_history_v1
Revises: block_3_indexing_models
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "chat_session_history_v1"
down_revision = "block_3_indexing_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_session_list", "chat_sessions", ["last_message_at", "id"], unique=False)

    op.create_table(
        "chat_turns",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("client_turn_id", sa.UUID(), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("document_scope_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.Text(), nullable=True),
        sa.Column("failure_detail_safe", sa.Text(), nullable=True),
        sa.CheckConstraint("state IN ('PENDING','STREAMING','COMPLETED','FAILED','CANCELLED')", name="ck_chat_turn_state"),
        sa.CheckConstraint("state <> 'COMPLETED' OR completed_at IS NOT NULL", name="ck_chat_turn_completed_at"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "client_turn_id", name="uq_chat_turn_session_client"),
    )
    op.create_index("ix_chat_turn_session_created", "chat_turns", ["session_id", "created_at"], unique=False)
    op.create_index(
        "uq_chat_turn_one_active_per_session",
        "chat_turns",
        ["session_id"],
        unique=True,
        postgresql_where=sa.text("state IN ('PENDING', 'STREAMING')"),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("turn_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("sequence_no", sa.BigInteger(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("delivery_state", sa.String(length=24), nullable=False),
        sa.Column("answer_status", sa.String(length=32), nullable=True),
        sa.Column("model_id", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("prompt_hash", sa.String(length=64), nullable=True),
        sa.Column("index_version", sa.Text(), nullable=True),
        sa.Column("context_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("generation_latency_ms", sa.Integer(), nullable=True),
        sa.Column("generation_metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('USER','ASSISTANT')", name="ck_chat_message_role"),
        sa.CheckConstraint("delivery_state IN ('COMMITTED','STREAMING','COMPLETED','FAILED','CANCELLED')", name="ck_chat_message_delivery_state"),
        sa.CheckConstraint("answer_status IS NULL OR answer_status IN ('ANSWERABLE','INSUFFICIENT_EVIDENCE')", name="ck_chat_message_answer_status"),
        sa.CheckConstraint("delivery_state <> 'COMPLETED' OR finalized_at IS NOT NULL", name="ck_chat_message_completed_finalized"),
        sa.CheckConstraint("delivery_state NOT IN ('FAILED','CANCELLED') OR answer_status IS NULL", name="ck_chat_message_terminal_answer_status"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["turn_id"], ["chat_turns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "sequence_no", name="uq_chat_message_session_sequence"),
    )
    op.create_index("ix_chat_message_session_sequence", "chat_messages", ["session_id", "sequence_no"], unique=False)
    op.create_index("ix_chat_message_turn", "chat_messages", ["turn_id"], unique=False)

    op.create_table(
        "message_citation_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("message_id", sa.UUID(), nullable=False),
        sa.Column("citation_label", sa.Text(), nullable=False),
        sa.Column("citation_order", sa.Integer(), nullable=False),
        sa.Column("original_document_id", sa.UUID(), nullable=True),
        sa.Column("original_chunk_id", sa.UUID(), nullable=True),
        sa.Column("original_legal_unit_id", sa.UUID(), nullable=True),
        sa.Column("document_title", sa.Text(), nullable=True),
        sa.Column("document_filename", sa.Text(), nullable=True),
        sa.Column("document_sha256", sa.String(length=64), nullable=True),
        sa.Column("chunk_content_sha256", sa.String(length=64), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("article", sa.Text(), nullable=True),
        sa.Column("clause", sa.Text(), nullable=True),
        sa.Column("point", sa.Text(), nullable=True),
        sa.Column("evidence_text", sa.Text(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provenance_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("snapshot_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("citation_order > 0", name="ck_chat_citation_order_positive"),
        sa.CheckConstraint("snapshot_version > 0", name="ck_chat_citation_snapshot_version_positive"),
        sa.ForeignKeyConstraint(["message_id"], ["chat_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", "citation_label", name="uq_chat_citation_message_label"),
        sa.UniqueConstraint("message_id", "citation_order", name="uq_chat_citation_message_order"),
    )
    op.create_index("ix_chat_citation_message", "message_citation_snapshots", ["message_id", "citation_order"], unique=False)


def downgrade() -> None:
    op.drop_table("message_citation_snapshots")
    op.drop_table("chat_messages")
    op.drop_table("chat_turns")
    op.drop_table("chat_sessions")
