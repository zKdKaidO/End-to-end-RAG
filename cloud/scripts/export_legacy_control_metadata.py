"""Read-only, metadata-only export to plan a Cloudflare control-plane migration.

This deliberately excludes passwords, sessions, documents, manifests, chunks,
embeddings, MinIO objects, prompts, context, answers, and private keys. Device
public keys are retained solely to assess whether existing paired devices can
be preserved after an approved account password-reset migration.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import create_engine, text


def value(value: object) -> object:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def rows(connection, statement: str) -> list[dict[str, object]]:
    return [{key: value(item) for key, item in row.items()} for row in connection.execute(text(statement)).mappings()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Export only account/device public metadata; performs no migration.")
    parser.add_argument("--database-url", required=True, help="Legacy PostgreSQL URL; never place it in shell history for production.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    engine = create_engine(args.database_url)
    with engine.connect() as connection:
        users = rows(connection, "SELECT id::text AS id, email, role, status, created_at FROM users ORDER BY created_at")
        devices = rows(connection, "SELECT id::text AS id, owner_user_id::text AS owner_user_id, public_key AS public_key_b64, friendly_label, credential_epoch, protocol_version, runtime_version, revoked_at, created_at, updated_at FROM compute_devices ORDER BY created_at")

    output = {
        "format": "zkd-control-metadata-export-v1",
        "account_action_required": "Reset/provision passwords as PBKDF2 records; Argon2 hashes are intentionally omitted.",
        "users": users,
        "devices": devices,
        "excluded": ["password_hash", "sessions", "pairing_tokens", "documents", "manifests", "chunks", "embeddings", "objects", "prompts", "context", "answers", "private_keys"],
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
