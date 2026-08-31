from __future__ import annotations

import json
from pathlib import Path

from redis import Redis
from rq import Worker
from sqlalchemy import text

from app.core.config import DeploymentProfile, settings
from app.db.database import engine
from app.indexing.artifact import CanonicalEmbeddingArtifactError, validate_canonical_e5_artifact
from app.deployment.model import ModelProvisioningError, verify_expected_model
from app.deployment.preflight import DeploymentPreflightError, validate_deployment_configuration
from app.deployment.release import expected_alembic_head
from app.deployment.tombstones import DeletionTombstoneStore
from app.storage.minio_client import minio_client


def _control_path(name: str) -> Path:
    return Path(settings.RECOVERY_CONTROL_DIR).resolve() / name


def set_recovery_mode(reason: str) -> None:
    path = _control_path("RECOVERY_MODE")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(reason.strip() or "RECOVERY", encoding="utf-8")


def clear_recovery_mode() -> None:
    _control_path("RECOVERY_MODE").unlink(missing_ok=True)


def readiness_report() -> dict:
    checks: dict[str, dict] = {}
    blockers: list[str] = []

    try:
        validate_deployment_configuration()
        checks["configuration"] = {"ok": True}
    except DeploymentPreflightError as exc:
        checks["configuration"] = {"ok": False, "reason": str(exc)}
        blockers.append(str(exc))

    recovery_mode = _control_path("RECOVERY_MODE")
    if recovery_mode.exists():
        checks["recovery_mode"] = {"ok": False, "reason": "RECOVERY_IN_PROGRESS"}
        blockers.append("RECOVERY_IN_PROGRESS")
    else:
        checks["recovery_mode"] = {"ok": True}

    try:
        validate_canonical_e5_artifact(settings.EMBEDDING_MODEL_CACHE_DIR)
        checks["embedding_artifact"] = {"ok": True}
    except CanonicalEmbeddingArtifactError as exc:
        checks["embedding_artifact"] = {"ok": False, "reason": str(exc)}
        blockers.append(str(exc))

    try:
        profile = settings.resolved_deployment_profile()
    except ValueError:
        profile = None

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            vector_version = connection.execute(
                text("SELECT extversion FROM pg_extension WHERE extname='vector'")
            ).scalar_one_or_none()
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
        expected = expected_alembic_head()
        ok = bool(vector_version) and revision == expected
        checks["postgresql"] = {
            "ok": ok, "pgvector": vector_version, "alembic_revision": revision, "expected_head": expected
        }
        if not vector_version:
            blockers.append("PGVECTOR_NOT_AVAILABLE")
        if revision != expected:
            blockers.append("MIGRATION_HEAD_MISMATCH")
    except Exception:
        checks["postgresql"] = {"ok": False, "reason": "POSTGRESQL_UNAVAILABLE"}
        blockers.append("POSTGRESQL_UNAVAILABLE")

    try:
        redis = Redis.from_url(settings.REDIS_URL)
        redis.ping()
        workers = Worker.all(connection=redis)
        worker_queues = sorted({queue.name for worker in workers for queue in worker.queues})
        required = {"ingestion", "document-processing", "document-indexing", "account-deletion", "document-gc"}
        worker_required = profile in {DeploymentProfile.SELF_HOSTED, DeploymentProfile.CLOUD_CONTROL_PLANE}
        worker_ok = not worker_required or required.issubset(set(worker_queues))
        checks["redis_workers"] = {"ok": worker_ok, "queues": worker_queues}
        if not worker_ok:
            blockers.append("REQUIRED_WORKERS_UNAVAILABLE")
    except Exception:
        checks["redis_workers"] = {"ok": False, "reason": "REDIS_UNAVAILABLE"}
        blockers.append("REDIS_UNAVAILABLE")

    minio_ok = minio_client.check_health()
    checks["minio"] = {"ok": minio_ok}
    if not minio_ok:
        blockers.append("MINIO_UNAVAILABLE")

    if profile is DeploymentProfile.CLOUD_CONTROL_PLANE:
        # P1 deliberately keeps generation transitional until P4. The cloud
        # control plane still validates its configured endpoint at preflight,
        # but readiness must not make a local Qwen runtime mandatory.
        checks["model"] = {"ok": True, "required": False, "reason": "P4_GENERATION_TRANSITION"}
    else:
        try:
            model = verify_expected_model()
            checks["model"] = {"ok": True, "name": model.name, "digest": model.digest}
        except ModelProvisioningError as exc:
            checks["model"] = {"ok": False, "reason": str(exc)}
            blockers.append(str(exc))

    report_path = _control_path("reconciliation-latest.json")
    if report_path.exists():
        try:
            reconciliation = json.loads(report_path.read_text(encoding="utf-8"))
            missing = int(reconciliation.get("missing_count", 0))
            mismatches = int(reconciliation.get("hash_mismatch_count", 0))
            checks["reconciliation"] = {
                "ok": missing == 0 and mismatches == 0,
                "missing": missing,
                "hash_mismatch": mismatches,
                "orphans": int(reconciliation.get("orphan_count", 0)),
            }
            if missing:
                blockers.append("MISSING_OBJECT")
            if mismatches:
                blockers.append("HASH_MISMATCH")
        except Exception:
            checks["reconciliation"] = {"ok": False, "reason": "RECONCILIATION_REPORT_INVALID"}
            blockers.append("RECONCILIATION_REPORT_INVALID")

    try:
        DeletionTombstoneStore().assert_available()
        checks["deletion_ledger"] = {"ok": True}
    except Exception:
        checks["deletion_ledger"] = {"ok": False, "reason": "DELETION_LEDGER_UNAVAILABLE"}
        blockers.append("DELETION_LEDGER_UNAVAILABLE")

    return {"status": "ready" if not blockers else "not_ready", "blockers": sorted(set(blockers)), "checks": checks}
