"""Add Auth + Authorization V1 product access layer.

Revision ID: auth_authorization_v1
Revises: chat_session_history_v1
"""

from alembic import op
import sqlalchemy as sa


revision = "auth_authorization_v1"
down_revision = "chat_session_history_v1"
branch_labels = None
depends_on = None

LEGACY_USER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("normalized_email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('USER','ADMIN')", name="ck_user_role"),
        sa.CheckConstraint("status IN ('ACTIVE','DISABLED','DELETING')", name="ck_user_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_email", name="uq_users_normalized_email"),
    )
    op.execute(sa.text("""
        INSERT INTO users (id, email, normalized_email, password_hash, role, status,
                           must_change_password, created_at, updated_at)
        VALUES (:id, 'legacy-system@local.invalid', 'legacy-system@local.invalid',
                '!disabled-migration-principal!', 'ADMIN', 'DISABLED', false, now(), now())
    """).bindparams(id=LEGACY_USER_ID))

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
    )
    op.create_index("ix_auth_session_user_active", "auth_sessions", ["user_id", "expires_at", "revoked_at"])

    op.create_table(
        "document_access_grants",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("document_id", "user_id"),
    )
    op.create_index("ix_document_access_user_document", "document_access_grants", ["user_id", "document_id"])
    op.create_index("ix_document_access_document_user", "document_access_grants", ["document_id", "user_id"])

    op.create_table(
        "global_document_access",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("granted_by_user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("document_id"),
    )
    op.execute(sa.text("""
        INSERT INTO global_document_access (document_id, granted_by_user_id, created_at)
        SELECT id, :id, now() FROM documents
    """).bindparams(id=LEGACY_USER_ID))

    op.create_table(
        "account_deletion_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("subject_user_id", sa.UUID(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("failure_code", sa.Text(), nullable=True),
        sa.Column("failure_detail_safe", sa.Text(), nullable=True),
        sa.CheckConstraint("state IN ('PENDING','QUEUED','RUNNING','COMPLETED','FAILED')", name="ck_account_deletion_state"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_account_deletion_one_active", "account_deletion_jobs", ["subject_user_id"], unique=True,
        postgresql_where=sa.text("state IN ('PENDING','QUEUED','RUNNING','FAILED')"),
    )
    op.create_table(
        "account_deletion_document_refs",
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("failure_code", sa.Text(), nullable=True),
        sa.Column("failure_detail_safe", sa.Text(), nullable=True),
        sa.CheckConstraint("state IN ('PENDING','RETAINED_REFERENCED','DELETED','FAILED')", name="ck_account_deletion_document_state"),
        sa.ForeignKeyConstraint(["job_id"], ["account_deletion_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id", "document_id"),
        sa.UniqueConstraint("job_id", "document_id", name="uq_account_deletion_document"),
    )
    op.create_index("ix_account_deletion_document_state", "account_deletion_document_refs", ["job_id", "state"])

    op.add_column("chat_sessions", sa.Column("user_id", sa.UUID(), nullable=True))
    op.execute(sa.text("UPDATE chat_sessions SET user_id = :id WHERE user_id IS NULL").bindparams(id=LEGACY_USER_ID))
    op.alter_column("chat_sessions", "user_id", nullable=False)
    op.create_foreign_key("fk_chat_sessions_user", "chat_sessions", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_chat_session_user_list", "chat_sessions", ["user_id", "last_message_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_chat_session_user_list", table_name="chat_sessions")
    op.drop_constraint("fk_chat_sessions_user", "chat_sessions", type_="foreignkey")
    op.drop_column("chat_sessions", "user_id")
    op.drop_table("account_deletion_document_refs")
    op.drop_table("account_deletion_jobs")
    op.drop_table("global_document_access")
    op.drop_table("document_access_grants")
    op.drop_table("auth_sessions")
    op.drop_table("users")
