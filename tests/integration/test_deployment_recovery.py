import hashlib
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.deployment.backup import BackupError, _write_checksums, apply_retention, verify_backup
from app.deployment.barrier import BackupBarrierTimeout, cross_store_barrier
from app.deployment.preflight import DeploymentPreflightError, validate_deployment_configuration
from app.deployment.reconcile import _stale, reconcile_cross_store
from app.deployment.restore import RestoreError, _filtered_restore_list, restore_backup
from app.deployment.tombstones import DeletionTombstoneStore


def test_production_preflight_rejects_insecure_cookie_and_backup_policy(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DEPLOYMENT_PROFILE", "production")
    monkeypatch.setattr(settings, "RECOVERY_CONTROL_DIR", str(tmp_path / "control"))
    monkeypatch.setattr(settings, "AUTH_COOKIE_SECURE", False)
    with pytest.raises(DeploymentPreflightError, match="INSECURE_PRODUCTION_COOKIE"):
        validate_deployment_configuration()

    monkeypatch.setattr(settings, "AUTH_COOKIE_SECURE", True)
    monkeypatch.setattr(settings, "SECURITY_HSTS_ENABLED", True)
    monkeypatch.setattr(settings, "AUTH_TRUSTED_ORIGINS", "https://rag.example.test")
    monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", "172.16.0.0/12")
    monkeypatch.setattr(settings, "RELEASE_ID", "release-test")
    monkeypatch.setattr(settings, "EXPECTED_MODEL_DIGEST", "a" * 64)
    monkeypatch.setattr(settings, "BACKUP_DESTINATION", str(tmp_path / "backup"))
    monkeypatch.setattr(settings, "BACKUP_DESTINATION_ENCRYPTED", False)
    monkeypatch.setattr(settings, "BACKUP_DESTINATION_SEPARATE_FAILURE_DOMAIN", True)
    with pytest.raises(DeploymentPreflightError, match="BACKUP_DESTINATION_ENCRYPTION_REQUIRED"):
        validate_deployment_configuration()

    monkeypatch.setattr(settings, "BACKUP_DESTINATION_ENCRYPTED", True)
    assert validate_deployment_configuration().production is True


def test_tombstone_ledger_is_idempotent_external_and_time_filterable(tmp_path):
    store = DeletionTombstoneStore(tmp_path)
    before = datetime(2026, 1, 1, tzinfo=timezone.utc)
    requested = datetime(2026, 1, 2, tzinfo=timezone.utc)
    store.record("00000000-0000-0000-0000-000000000010", "00000000-0000-0000-0000-000000000020", requested)
    store.record("00000000-0000-0000-0000-000000000010", "00000000-0000-0000-0000-000000000020", requested)
    assert len(store.read_all()) == 1
    assert len(store.newer_than(before)) == 1
    assert store.contains("00000000-0000-0000-0000-000000000020")
    assert "email" not in store.path.read_text(encoding="utf-8")


def test_cross_store_barrier_excludes_mutation_and_recovers():
    with cross_store_barrier(exclusive=True, timeout_seconds=2):
        with pytest.raises(BackupBarrierTimeout):
            with cross_store_barrier(exclusive=False, timeout_seconds=0.2):
                pass
    with cross_store_barrier(exclusive=False, timeout_seconds=2):
        pass


def _fake_backup(root: Path, backup_id: str, completed_at: datetime):
    target = root / backup_id
    target.mkdir()
    (target / "postgres.dump").write_bytes(b"dump")
    (target / "minio-manifest.json").write_text("[]", encoding="utf-8")
    (target / "manifest.json").write_text(json.dumps({
        "backup_id": backup_id,
        "backup_format_version": 1,
        "completed_at": completed_at.isoformat(),
    }), encoding="utf-8")
    _write_checksums(target)
    (target / "COMPLETE").write_text(backup_id, encoding="utf-8")


def test_backup_complete_checksum_and_whole_set_retention(monkeypatch, tmp_path):
    first = "20260101T000000Z-aaaaaaaa"
    second = "20260102T000000Z-bbbbbbbb"
    _fake_backup(tmp_path, first, datetime(2026, 1, 1, tzinfo=timezone.utc))
    _fake_backup(tmp_path, second, datetime(2026, 1, 2, tzinfo=timezone.utc))
    assert verify_backup(tmp_path, first)["backup_id"] == first
    (tmp_path / first / "postgres.dump").write_bytes(b"tampered")
    with pytest.raises(BackupError, match="CHECKSUM_MISMATCH"):
        verify_backup(tmp_path, first)

    monkeypatch.setattr(settings, "BACKUP_KEEP_LAST", 1)
    monkeypatch.setattr(settings, "BACKUP_RETENTION_DAYS", 0)
    plan = apply_retention(backup_root=tmp_path, dry_run=True, now=datetime(2026, 1, 3, tzinfo=timezone.utc))
    assert plan["delete"] == [first]
    apply_retention(backup_root=tmp_path, dry_run=False, now=datetime(2026, 1, 3, tzinfo=timezone.utc))
    assert not (tmp_path / first).exists()
    assert (tmp_path / second / "COMPLETE").exists()


def test_backup_rejects_files_added_after_complete(tmp_path):
    backup_id = "20260101T000000Z-aaaaaaaa"
    _fake_backup(tmp_path, backup_id, datetime(2026, 1, 1, tzinfo=timezone.utc))
    (tmp_path / backup_id / "operator-output.json").write_text("{}", encoding="utf-8")
    with pytest.raises(BackupError, match="BACKUP_FILE_SET_MISMATCH"):
        verify_backup(tmp_path, backup_id)


class _Response:
    def __init__(self, value: bytes):
        self.value = io.BytesIO(value)
    def read(self, size=-1):
        return self.value.read(size)
    def close(self):
        pass
    def release_conn(self):
        pass


def test_reconciliation_classifies_healthy_hash_mismatch_and_orphan(monkeypatch, tmp_path):
    good = b"good-pdf"
    rows = [
        SimpleNamespace(id="00000000-0000-0000-0000-000000000001", sha256=hashlib.sha256(good).hexdigest(), storage_uri="x"),
        SimpleNamespace(id="00000000-0000-0000-0000-000000000002", sha256="0" * 64, storage_uri="x"),
    ]
    class FakeDb:
        def execute(self, _stmt): return SimpleNamespace(all=lambda: rows)
        def close(self): pass
    objects = {
        f"{rows[0].id}/original.pdf": good,
        f"{rows[1].id}/original.pdf": b"wrong",
    }
    class FakeClient:
        def get_object(self, _bucket, key): return _Response(objects[key])
        def list_objects(self, _bucket, recursive=True):
            return [SimpleNamespace(object_name=key) for key in [*objects, "orphan/original.pdf"]]
    monkeypatch.setattr("app.deployment.reconcile.SessionLocal", lambda: FakeDb())
    monkeypatch.setattr("app.deployment.reconcile.minio_client", SimpleNamespace(client=FakeClient(), bucket="documents"))
    monkeypatch.setattr(settings, "RECOVERY_CONTROL_DIR", str(tmp_path))
    report = reconcile_cross_store(output=tmp_path / "report.json")
    assert report["present_count"] == 2
    assert report["hash_mismatch_count"] == 1
    assert report["orphan_count"] == 1
    assert report["readiness_blocked"] is True


def test_hnsw_restore_list_defers_only_canonical_index(monkeypatch, tmp_path):
    toc = "\n".join([
        "; archive",
        "100; 1259 1 TABLE public chunk_indexes postgres",
        "200; 1259 2 INDEX public ix_chunk_indexes_embedding postgres",
        "201; 1259 3 INDEX public ix_chunk_indexes_lexical_tsv postgres",
    ])
    monkeypatch.setattr("app.deployment.restore.subprocess.run", lambda *a, **k: SimpleNamespace(stdout=toc))
    output = tmp_path / "filtered.list"
    assert _filtered_restore_list(tmp_path / "dump", output) == 1
    text = output.read_text(encoding="utf-8")
    assert ";200; 1259 2 INDEX public ix_chunk_indexes_embedding" in text
    assert "\n201; 1259 3 INDEX public ix_chunk_indexes_lexical_tsv" in text


def test_restore_operator_guards_run_before_mutation(tmp_path):
    with pytest.raises(RestoreError, match="EXPLICIT_RECOVERY_ENVIRONMENT_REQUIRED"):
        restore_backup(
            backup_root=tmp_path,
            backup_id="20260101T000000Z-aaaaaaaa",
            environment_name="development",
            confirmation="RESTORE:20260101T000000Z-aaaaaaaa",
            ollama_stopped_ack=True,
        )


def test_job_staleness_is_deterministic():
    now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    assert _stale(now - timedelta(seconds=901), now=now, seconds=900)
    assert not _stale(now - timedelta(seconds=899), now=now, seconds=900)
    assert _stale(None, now=now, seconds=900)


def test_deployment_topology_and_pgvector_bootstrap_static_contract():
    dev = Path("docker-compose.yml").read_text(encoding="utf-8")
    prod = Path("deployment/docker-compose.production.yml").read_text(encoding="utf-8")
    init = Path("postgres/initdb/01-create-extension.sql").read_text(encoding="utf-8")
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS vector" in init
    assert "service_completed_successfully" in dev and "migration-check" in dev
    assert "internal: true" in prod
    assert "AUTH_COOKIE_SECURE: \"true\"" in prod
    assert "provision-model" in prod and "pull qwen3.5:9b" in prod
    assert "postgres:15-bookworm AS postgres15_tools" in dockerfile
    assert "/usr/lib/postgresql/15/bin/pg_dump" in dockerfile
    assert "ports:" not in prod.split("  postgres:", 1)[1].split("  redis:", 1)[0]
