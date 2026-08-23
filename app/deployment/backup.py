from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import inspect, select, text
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.db.database import SessionLocal, engine
from app.deployment.barrier import cross_store_barrier
from app.deployment.constants import BACKUP_FORMAT_VERSION
from app.deployment.model import verify_expected_model
from app.deployment.preflight import validate_deployment_configuration
from app.deployment.reconcile import reconcile_cross_store
from app.deployment.release import collect_release_manifest
from app.models.document import Document
from app.storage.minio_client import minio_client


BACKUP_ID_PATTERN = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$")


class BackupError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def new_backup_id(now: datetime | None = None) -> str:
    value = now or _now()
    return value.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]


def validate_backup_id(backup_id: str) -> str:
    if not BACKUP_ID_PATTERN.fullmatch(backup_id):
        raise BackupError("INVALID_BACKUP_ID")
    return backup_id


def _database_environment() -> tuple[dict[str, str], list[str]]:
    url = make_url(settings.DATABASE_URL)
    environment = os.environ.copy()
    environment.update({
        "PGHOST": str(url.host or "localhost"),
        "PGPORT": str(url.port or 5432),
        "PGUSER": str(url.username or "postgres"),
        "PGPASSWORD": str(url.password or ""),
    })
    return environment, ["--dbname", str(url.database)]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _table_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    with engine.connect() as connection:
        for table_name in sorted(inspect(connection).get_table_names(schema="public")):
            if table_name == "alembic_version":
                continue
            safe_name = table_name.replace('"', '""')
            counts[table_name] = int(connection.execute(text(f'SELECT count(*) FROM "{safe_name}"')).scalar_one())
    return counts


def _mirror_minio(destination: Path) -> tuple[list[dict], int]:
    rows: list[dict] = []
    total_bytes = 0
    for item in minio_client.client.list_objects(minio_client.bucket, recursive=True):
        target = destination / minio_client.bucket / Path(item.object_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        minio_client.client.fget_object(minio_client.bucket, item.object_name, str(target))
        size = target.stat().st_size
        total_bytes += size
        rows.append({
            "bucket": minio_client.bucket,
            "object_key": item.object_name,
            "size": size,
            "sha256": _sha256_file(target),
        })
    rows.sort(key=lambda row: (row["bucket"], row["object_key"]))
    return rows, total_bytes


def _write_checksums(root: Path) -> Path:
    checksum_path = root / "checksums.sha256"
    files = sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.name not in {"checksums.sha256", "COMPLETE"}
    )
    lines = [f"{_sha256_file(path)}  {path.relative_to(root).as_posix()}" for path in files]
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return checksum_path


def verify_backup(backup_root: Path, backup_id: str, *, require_complete: bool = True) -> dict:
    validate_backup_id(backup_id)
    root = backup_root.resolve() / backup_id
    if require_complete and not (root / "COMPLETE").is_file():
        raise BackupError("BACKUP_INCOMPLETE")
    manifest_path = root / "manifest.json"
    checksums_path = root / "checksums.sha256"
    if not manifest_path.is_file() or not checksums_path.is_file():
        raise BackupError("BACKUP_METADATA_MISSING")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("backup_id") != backup_id or manifest.get("backup_format_version") != BACKUP_FORMAT_VERSION:
        raise BackupError("BACKUP_MANIFEST_INCOMPATIBLE")
    listed: set[str] = set()
    for line in checksums_path.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        listed.add(relative)
        target = (root / relative).resolve()
        if root.resolve() not in target.parents or not target.is_file():
            raise BackupError("BACKUP_CHECKSUM_TARGET_INVALID")
        if _sha256_file(target) != expected:
            raise BackupError(f"BACKUP_CHECKSUM_MISMATCH:{relative}")
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name not in {"checksums.sha256", "COMPLETE"}
    }
    if actual != listed:
        raise BackupError("BACKUP_FILE_SET_MISMATCH")
    return manifest


def create_backup(*, backup_root: Path | None = None, backup_id: str | None = None) -> dict:
    validate_deployment_configuration()
    started = _now()
    identifier = validate_backup_id(backup_id) if backup_id else new_backup_id(started)
    destination = (backup_root or Path(settings.BACKUP_DESTINATION)).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    root = destination / identifier
    if root.exists():
        raise BackupError("BACKUP_ID_ALREADY_EXISTS")
    root.mkdir()
    dump_path = root / "postgres.dump"
    minio_root = root / "minio"
    minio_root.mkdir()

    try:
        with cross_store_barrier(exclusive=True, timeout_seconds=300):
            snapshot_at = _now()
            environment, database_args = _database_environment()
            subprocess.run(
                ["pg_dump", "--format=custom", "--no-owner", "--no-privileges", *database_args, "--file", str(dump_path)],
                check=True,
                env=environment,
            )
            object_rows, minio_bytes = _mirror_minio(minio_root)
            minio_manifest_path = root / "minio-manifest.json"
            minio_manifest_path.write_text(json.dumps(object_rows, indent=2, sort_keys=True), encoding="utf-8")
            reconciliation = reconcile_cross_store(
                backup_id=identifier, output=root / "reconciliation.json"
            )
            if reconciliation["readiness_blocked"]:
                raise BackupError("CROSS_STORE_RECONCILIATION_FAILED")

            release = collect_release_manifest()
            model = verify_expected_model()
            with SessionLocal() as db:
                document_count = int(db.scalar(select(text("count(*)")).select_from(Document)) or 0)
            completed_at = _now()
            manifest = {
                "backup_format_version": BACKUP_FORMAT_VERSION,
                "backup_id": identifier,
                "complete": True,
                "state": "BACKUP_INTEGRITY_VERIFIED",
                "started_at": started.isoformat(),
                "snapshot_at": snapshot_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "release_id": release["release_id"],
                "git_commit_sha": release["git_commit_sha"],
                "alembic_revision": release["alembic_revision"],
                "postgresql_version": release["postgresql_version"],
                "pgvector_version": release["pgvector_version"],
                "minio_version": settings.MINIO_VERSION,
                "database_dump_sha256": _sha256_file(dump_path),
                "database_dump_bytes": dump_path.stat().st_size,
                "minio_manifest_sha256": _sha256_file(minio_manifest_path),
                "minio_object_count": len(object_rows),
                "minio_total_bytes": minio_bytes,
                "document_count": document_count,
                "table_counts": _table_counts(),
                "snapshot_consistency": "POSTGRES_ADVISORY_EXCLUSIVE_CROSS_STORE_BARRIER",
                "production_model_name": settings.GENERATION_MODEL_ID,
                "production_model_digest": model.digest,
                "model_artifact_included": False,
                "redis_backup_included": False,
                "duration_seconds": round((completed_at - started).total_seconds(), 3),
            }
            (root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
            _write_checksums(root)
            verify_backup(destination, identifier, require_complete=False)
            (root / "COMPLETE").write_text(f"{identifier}\n", encoding="utf-8")
            return manifest
    except Exception:
        # Deliberately retain the incomplete set for operator diagnosis. It is
        # never eligible for normal restore because COMPLETE is absent.
        (root / "COMPLETE").unlink(missing_ok=True)
        raise


def apply_retention(*, backup_root: Path | None = None, dry_run: bool = True, now: datetime | None = None) -> dict:
    root = (backup_root or Path(settings.BACKUP_DESTINATION)).resolve()
    if not root.exists():
        return {"dry_run": dry_run, "delete": [], "kept": []}
    current = now or _now()
    complete: list[tuple[Path, datetime]] = []
    for path in root.iterdir():
        if path.is_dir() and BACKUP_ID_PATTERN.fullmatch(path.name) and (path / "COMPLETE").is_file():
            manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
            complete.append((path, datetime.fromisoformat(manifest["completed_at"])))
    complete.sort(key=lambda item: item[1], reverse=True)
    protected = {path for path, _ in complete[: settings.BACKUP_KEEP_LAST]}
    expired = [
        path for path, timestamp in complete
        if path not in protected and (current - timestamp).days >= settings.BACKUP_RETENTION_DAYS
    ]
    if not dry_run:
        for path in expired:
            if path.parent != root or not BACKUP_ID_PATTERN.fullmatch(path.name):
                raise BackupError("RETENTION_TARGET_GUARD_FAILED")
            shutil.rmtree(path)
    return {
        "dry_run": dry_run,
        "delete": [path.name for path in expired],
        "kept": [path.name for path, _ in complete if path not in expired],
    }
