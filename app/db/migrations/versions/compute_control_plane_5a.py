"""Add metadata-only ZKD Compute platform control plane.

Revision ID: compute_control_plane_5a
Revises: auth_authorization_v1
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "compute_control_plane_5a"
down_revision = "auth_authorization_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("compute_devices", sa.Column("id", sa.UUID(), nullable=False), sa.Column("owner_user_id", sa.UUID(), nullable=False), sa.Column("public_key", sa.String(128), nullable=False), sa.Column("friendly_label", sa.String(120)), sa.Column("credential_epoch", sa.Integer(), nullable=False), sa.Column("protocol_version", sa.String(64), nullable=False), sa.Column("runtime_version", sa.String(64), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True)), sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("public_key"))
    op.create_index("ix_compute_device_owner", "compute_devices", ["owner_user_id", "revoked_at"])
    op.create_table("compute_pairing_challenges", sa.Column("id", sa.UUID(), nullable=False), sa.Column("owner_user_id", sa.UUID(), nullable=False), sa.Column("token_hash", sa.String(64), nullable=False), sa.Column("confirmation_code_hash", sa.String(64), nullable=False), sa.Column("state", sa.String(32), nullable=False), sa.Column("pending_device_id", sa.UUID()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("consumed_at", sa.DateTime(timezone=True)), sa.Column("confirmed_at", sa.DateTime(timezone=True)), sa.CheckConstraint("state IN ('PENDING','AWAITING_CONFIRMATION','CONFIRMED','CONSUMED','EXPIRED','CANCELLED')", name="ck_compute_pairing_state"), sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("token_hash"))
    op.create_index("ix_compute_pairing_owner_expiry", "compute_pairing_challenges", ["owner_user_id", "expires_at"])
    op.create_table("compute_presence", sa.Column("device_id", sa.UUID(), nullable=False), sa.Column("state", sa.String(32), nullable=False), sa.Column("protocol_version", sa.String(64), nullable=False), sa.Column("runtime_version", sa.String(64), nullable=False), sa.Column("endpoint_generation", sa.String(128), nullable=False), sa.Column("endpoint_port", sa.Integer()), sa.Column("capabilities_json", postgresql.JSONB(), nullable=False), sa.Column("provider_metadata_json", postgresql.JSONB(), nullable=False), sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["device_id"], ["compute_devices.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("device_id"))
    op.create_table("local_document_manifests", sa.Column("id", sa.UUID(), nullable=False), sa.Column("owner_user_id", sa.UUID(), nullable=False), sa.Column("device_id", sa.UUID(), nullable=False), sa.Column("document_id", sa.UUID(), nullable=False), sa.Column("filename", sa.String(255)), sa.Column("size_bytes", sa.Integer()), sa.Column("preparation_state", sa.String(32), nullable=False), sa.Column("index_state", sa.String(32), nullable=False), sa.Column("chunk_count", sa.Integer()), sa.Column("artifact_id", sa.UUID()), sa.Column("artifact_version", sa.String(128)), sa.Column("artifact_profile_fingerprint", sa.String(64)), sa.Column("local_availability", sa.String(32), nullable=False), sa.Column("error_code", sa.String(96)), sa.Column("error_message", sa.String(512)), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["device_id"], ["compute_devices.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("owner_user_id", "device_id", "document_id", name="uq_local_manifest_owner_device_document"))
    op.create_index("ix_local_manifest_owner_document", "local_document_manifests", ["owner_user_id", "document_id"])
    op.create_table("compute_replay_nonces", sa.Column("device_id", sa.UUID(), nullable=False), sa.Column("nonce_hash", sa.String(64), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["device_id"], ["compute_devices.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("device_id", "nonce_hash"))
    op.create_table("compute_local_session_grants", sa.Column("id", sa.UUID(), nullable=False), sa.Column("owner_user_id", sa.UUID(), nullable=False), sa.Column("device_id", sa.UUID(), nullable=False), sa.Column("credential_epoch", sa.Integer(), nullable=False), sa.Column("endpoint_generation", sa.String(128), nullable=False), sa.Column("origin", sa.String(255), nullable=False), sa.Column("browser_nonce_hash", sa.String(64), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["device_id"], ["compute_devices.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))


def downgrade() -> None:
    op.drop_table("compute_local_session_grants"); op.drop_table("compute_replay_nonces"); op.drop_table("local_document_manifests"); op.drop_table("compute_presence"); op.drop_table("compute_pairing_challenges"); op.drop_table("compute_devices")
