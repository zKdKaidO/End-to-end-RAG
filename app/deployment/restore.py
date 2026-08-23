from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from app.core.config import settings
from app.db.database import engine
from app.deployment.backup import BackupError, _database_environment, verify_backup
from app.deployment.constants import BACKUP_FORMAT_VERSION, HNSW_CREATE_SQL, HNSW_INDEX_NAME
from app.deployment.model import verify_expected_model
from app.deployment.readiness import clear_recovery_mode, set_recovery_mode
from app.deployment.reconcile import (
    reconcile_cross_store,
    reconcile_durable_jobs,
    replay_deletion_tombstones,
    revoke_all_auth_sessions,
)
from app.deployment.release import expected_alembic_head
from app.deployment.tombstones import DeletionTombstoneStore
from app.storage.minio_client import minio_client


class RestoreError(RuntimeError):
    pass


def verify_restore_compatibility(manifest: dict) -> dict:
    if manifest.get("backup_format_version") != BACKUP_FORMAT_VERSION:
        raise RestoreError("BACKUP_FORMAT_UNSUPPORTED")
    if manifest.get("alembic_revision") != expected_alembic_head():
        raise RestoreError("ALEMBIC_REVISION_INCOMPATIBLE")
    with engine.connect() as connection:
        current_major = int(connection.execute(text("SHOW server_version_num")).scalar_one()) // 10000
        vector_version = connection.execute(
            text("SELECT extversion FROM pg_extension WHERE extname='vector'")
        ).scalar_one_or_none()
    backup_major = int(str(manifest["postgresql_version"]).split(".", 1)[0])
    if current_major != backup_major:
        raise RestoreError("POSTGRES_MAJOR_INCOMPATIBLE")
    if vector_version != manifest.get("pgvector_version"):
        raise RestoreError("PGVECTOR_VERSION_INCOMPATIBLE")
    if manifest.get("minio_version") != settings.MINIO_VERSION:
        raise RestoreError("MINIO_FORMAT_VERSION_INCOMPATIBLE")
    if manifest.get("production_model_name") != settings.GENERATION_MODEL_ID:
        raise RestoreError("MODEL_IDENTITY_INCOMPATIBLE")
    expected_digest = settings.EXPECTED_MODEL_DIGEST.strip()
    if expected_digest and manifest.get("production_model_digest") != expected_digest:
        raise RestoreError("MODEL_DIGEST_INCOMPATIBLE")
    return {
        "postgres_major": current_major,
        "pgvector_version": vector_version,
        "alembic_revision": expected_alembic_head(),
        "compatible": True,
    }


def _filtered_restore_list(dump_path: Path, output: Path) -> int:
    result = subprocess.run(["pg_restore", "--list", str(dump_path)], check=True, text=True, capture_output=True)
    lines = result.stdout.splitlines()
    matches = 0
    filtered: list[str] = []
    marker = f" INDEX public {HNSW_INDEX_NAME} "
    for line in lines:
        if marker in line and not line.lstrip().startswith(";"):
            filtered.append(";" + line)
            matches += 1
        else:
            filtered.append(line)
    if matches != 1:
        raise RestoreError(f"HNSW_TOC_ENTRY_COUNT_INVALID:{matches}")
    output.write_text("\n".join(filtered) + "\n", encoding="utf-8")
    return matches


def restore_postgres(dump_path: Path, work_dir: Path) -> dict:
    restore_list = work_dir / "pg_restore.filtered.list"
    deferred = _filtered_restore_list(dump_path, restore_list)
    environment, database_args = _database_environment()
    started = time.monotonic()
    subprocess.run(
        [
            "pg_restore", "--clean", "--if-exists", "--no-owner", "--no-privileges",
            "--exit-on-error", "--use-list", str(restore_list), *database_args, str(dump_path),
        ],
        check=True,
        env=environment,
    )
    with engine.connect() as connection:
        vector_rows = int(connection.execute(text("SELECT count(*) FROM chunk_indexes")).scalar_one())
        hnsw_exists = bool(connection.execute(
            text("SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname=:name"),
            {"name": HNSW_INDEX_NAME},
        ).scalar_one_or_none())
    if hnsw_exists:
        raise RestoreError("HNSW_WAS_NOT_DEFERRED")
    return {
        "duration_seconds": round(time.monotonic() - started, 3),
        "hnsw_entries_deferred": deferred,
        "vector_rows_restored": vector_rows,
    }


def restore_minio(root: Path, minio_manifest: list[dict]) -> dict:
    if not minio_client.client.bucket_exists(minio_client.bucket):
        minio_client.client.make_bucket(minio_client.bucket)
    existing = list(minio_client.client.list_objects(minio_client.bucket, recursive=True))
    if existing:
        expected = {item["object_key"]: item["sha256"] for item in minio_manifest}
        actual: dict[str, str] = {}
        for item in existing:
            response = minio_client.client.get_object(minio_client.bucket, item.object_name)
            try:
                import hashlib
                digest = hashlib.sha256()
                for block in iter(lambda: response.read(1024 * 1024), b""):
                    digest.update(block)
                actual[item.object_name] = digest.hexdigest()
            finally:
                response.close()
                response.release_conn()
        if actual != expected:
            raise RestoreError("RESTORE_EXISTING_MINIO_NOT_EXACT_BACKUP_PAIR")
        return {
            "duration_seconds": 0.0,
            "objects_restored": 0,
            "bytes_restored": 0,
            "reused_existing_exact_pair": True,
        }
    started = time.monotonic()
    restored_bytes = 0
    for item in minio_manifest:
        if item["bucket"] != minio_client.bucket:
            raise RestoreError("MINIO_BUCKET_INCOMPATIBLE")
        source = root / "minio" / item["bucket"] / Path(item["object_key"])
        if not source.is_file():
            raise RestoreError("MINIO_BACKUP_OBJECT_MISSING")
        minio_client.client.fput_object(item["bucket"], item["object_key"], str(source), content_type="application/pdf")
        restored_bytes += source.stat().st_size
    return {
        "duration_seconds": round(time.monotonic() - started, 3),
        "objects_restored": len(minio_manifest),
        "bytes_restored": restored_bytes,
        "reused_existing_exact_pair": False,
    }


def rebuild_hnsw(*, ollama_stopped_ack: bool) -> dict:
    if not ollama_stopped_ack:
        raise RestoreError("OLLAMA_STOP_ACK_REQUIRED")
    memory = settings.RESTORE_MAINTENANCE_WORK_MEM
    if not re.fullmatch(r"[1-9][0-9]*(kB|MB|GB)", memory):
        raise RestoreError("INVALID_MAINTENANCE_WORK_MEM")
    workers = settings.RESTORE_MAX_PARALLEL_MAINTENANCE_WORKERS
    if workers < 0 or workers > 8:
        raise RestoreError("INVALID_PARALLEL_MAINTENANCE_WORKERS")
    started = time.monotonic()
    with engine.begin() as connection:
        exists = bool(connection.execute(
            text("SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname=:name"),
            {"name": HNSW_INDEX_NAME},
        ).scalar_one_or_none())
        if not exists:
            connection.execute(text("SELECT set_config('maintenance_work_mem', :value, true)"), {"value": memory})
            connection.execute(text("SELECT set_config('max_parallel_maintenance_workers', :value, true)"), {"value": str(workers)})
            connection.execute(text(HNSW_CREATE_SQL))
    return {
        "index": HNSW_INDEX_NAME,
        "created": not exists,
        "duration_seconds": round(time.monotonic() - started, 3),
        "maintenance_work_mem": memory,
        "max_parallel_maintenance_workers": workers,
        "ollama_running_during_rebuild": False,
    }


def restore_backup(
    *,
    backup_root: Path,
    backup_id: str,
    environment_name: str,
    confirmation: str,
    ollama_stopped_ack: bool,
    output: Path | None = None,
) -> dict:
    if environment_name not in {"recovery-test", "production-recovery"}:
        raise RestoreError("EXPLICIT_RECOVERY_ENVIRONMENT_REQUIRED")
    if confirmation != f"RESTORE:{backup_id}":
        raise RestoreError("RESTORE_CONFIRMATION_MISMATCH")
    root = backup_root.resolve() / backup_id
    manifest = verify_backup(backup_root.resolve(), backup_id)
    compatibility = verify_restore_compatibility(manifest)
    set_recovery_mode(f"RESTORE:{backup_id}")
    work_dir = Path(settings.RECOVERY_CONTROL_DIR).resolve() / "restore-runs" / backup_id
    work_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    result: dict = {
        "recovery_format_version": 1,
        "backup_id": backup_id,
        "environment": environment_name,
        "state": "RESTORE_IN_PROGRESS",
        "started_at": datetime.now().astimezone().isoformat(),
        "compatibility": compatibility,
    }
    try:
        postgres = restore_postgres(root / "postgres.dump", work_dir)
        minio_manifest = json.loads((root / "minio-manifest.json").read_text(encoding="utf-8"))
        minio = restore_minio(root, minio_manifest)
        reconciliation_started = time.monotonic()
        reconciliation = reconcile_cross_store(backup_id=backup_id, output=work_dir / "restore-reconciliation.json")
        reconciliation_duration = round(time.monotonic() - reconciliation_started, 3)
        if reconciliation["readiness_blocked"]:
            raise RestoreError("RESTORE_RECONCILIATION_BLOCKED")

        sessions_revoked = revoke_all_auth_sessions()
        snapshot_at = datetime.fromisoformat(manifest["snapshot_at"])
        tombstones = DeletionTombstoneStore().newer_than(snapshot_at)
        replay = replay_deletion_tombstones(tombstones, enqueue=False)
        if replay["count"]:
            from app.auth.worker import process_account_deletion
            for row in replay["replayed"]:
                if row.get("job_id"):
                    process_account_deletion(row["job_id"], request_id="disaster-recovery")

        jobs = reconcile_durable_jobs(output=work_dir / "job-reconciliation.json")
        hnsw = rebuild_hnsw(ollama_stopped_ack=ollama_stopped_ack)
        model = verify_expected_model()
        final_reconciliation = reconcile_cross_store(
            backup_id=backup_id, output=work_dir / "restore-reconciliation-final.json"
        )
        if final_reconciliation["readiness_blocked"]:
            raise RestoreError("FINAL_RECONCILIATION_BLOCKED")
        clear_recovery_mode()
        result.update({
            "state": "BACKUP_RESTORE_VERIFIED_PENDING_PRODUCT_E2E",
            "postgres": postgres,
            "minio": minio,
            "reconciliation": final_reconciliation,
            "reconciliation_duration_seconds": reconciliation_duration,
            "sessions_revoked": sessions_revoked,
            "deletion_tombstones": replay,
            "jobs": jobs,
            "hnsw": hnsw,
            "model": {"name": model.name, "digest": model.digest},
            "restore_duration_seconds": round(time.monotonic() - started, 3),
            "completed_at": datetime.now().astimezone().isoformat(),
        })
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        return result
    except Exception as exc:
        result.update({"state": "RESTORE_FAILED", "failure_code": type(exc).__name__, "failure_reason": str(exc)})
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        raise
