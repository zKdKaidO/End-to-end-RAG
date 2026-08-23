from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from redis import Redis
from sqlalchemy import text

from app.core.config import settings
from app.db.database import engine
from app.deployment.model import find_model_identity


def expected_alembic_head() -> str:
    return ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()


def current_alembic_revision() -> str | None:
    with engine.connect() as connection:
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()


def _git_sha() -> str:
    configured = os.environ.get("GIT_COMMIT_SHA", "").strip()
    if configured:
        return configured
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "UNKNOWN"


def _frontend_hash() -> str | None:
    root = Path("frontend/dist")
    if not root.exists():
        return None
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def collect_release_manifest() -> dict:
    with engine.connect() as connection:
        postgres_version = connection.execute(text("SHOW server_version")).scalar_one()
        pgvector_version = connection.execute(
            text("SELECT extversion FROM pg_extension WHERE extname='vector'")
        ).scalar_one_or_none()
    redis_version = Redis.from_url(settings.REDIS_URL, decode_responses=True).info("server").get("redis_version")
    model = find_model_identity()
    return {
        "release_manifest_version": 1,
        "release_id": settings.RELEASE_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit_sha": _git_sha(),
        "docker_image_identities": {},
        "alembic_revision": current_alembic_revision(),
        "alembic_expected_head": expected_alembic_head(),
        "postgresql_version": postgres_version,
        "pgvector_version": pgvector_version,
        "redis_version": redis_version,
        "minio_version": settings.MINIO_VERSION,
        "ollama_version": model.provider_version if model else None,
        "production_model_name": settings.GENERATION_MODEL_ID,
        "production_model_digest": model.digest if model else None,
        "frontend_build_sha256": _frontend_hash(),
    }


def write_release_manifest(path: Path) -> dict:
    data = collect_release_manifest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return data
