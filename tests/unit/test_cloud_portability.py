from pathlib import Path

import pytest

from app.core.config import DeploymentProfile, resolve_deployment_profile, settings
from app.deployment.preflight import DeploymentPreflightError, validate_deployment_configuration
from app.indexing.artifact import CanonicalEmbeddingArtifactError, validate_canonical_e5_artifact
from app.indexing.embedder import E5Embedder


def _canonical_e5_cache(root: Path) -> Path:
    revision = "0123456789abcdef"
    snapshot = root / "models--intfloat--multilingual-e5-base" / "snapshots" / revision
    snapshot.mkdir(parents=True, exist_ok=True)
    (root / "models--intfloat--multilingual-e5-base" / "refs").mkdir(exist_ok=True)
    (root / "models--intfloat--multilingual-e5-base" / "refs" / "main").write_text(
        revision, encoding="utf-8"
    )
    for filename in ("config.json", "modules.json", "tokenizer_config.json"):
        (snapshot / filename).write_text("{}", encoding="utf-8")
    (snapshot / "model.safetensors").write_bytes(b"canonical-test-artifact")
    return root


def _cloud_settings(monkeypatch, tmp_path: Path) -> None:
    values = {
        "DEPLOYMENT_PROFILE": "cloud_control_plane",
        "DATABASE_URL": "postgresql://user:password@postgres.example.test:5432/rag",
        "REDIS_URL": "rediss://:password@redis.example.test:6380/0",
        "MINIO_ENDPOINT": "objects.example.test:443",
        "MINIO_ACCESS_KEY": "access",
        "MINIO_SECRET_KEY": "secret",
        "MINIO_BUCKET": "documents",
        "MINIO_SECURE": True,
        "OLLAMA_BASE_URL": "https://generation.example.test",
        "AUTH_COOKIE_SECURE": True,
        "SECURITY_HSTS_ENABLED": True,
        "AUTH_TRUSTED_ORIGINS": "https://rag.example.test",
        "TRUSTED_PROXY_CIDRS": "10.0.0.0/8",
        "RELEASE_ID": "p1-test",
        "RECOVERY_CONTROL_DIR": str(tmp_path / "control"),
        "BACKUP_DESTINATION": str(tmp_path / "backup"),
        "BACKUP_DESTINATION_ENCRYPTED": True,
        "BACKUP_DESTINATION_SEPARATE_FAILURE_DOMAIN": True,
        "EMBEDDING_MODEL_CACHE_DIR": str(tmp_path / "e5-cache"),
    }
    _canonical_e5_cache(tmp_path / "e5-cache")
    for name, value in values.items():
        monkeypatch.setattr(settings, name, value)


def test_deployment_profiles_are_topology_values_with_legacy_aliases():
    assert resolve_deployment_profile("local_dev") is DeploymentProfile.LOCAL_DEV
    assert resolve_deployment_profile("pc_tunnel") is DeploymentProfile.PC_TUNNEL
    assert resolve_deployment_profile("cloud_control_plane") is DeploymentProfile.CLOUD_CONTROL_PLANE
    assert resolve_deployment_profile("development") is DeploymentProfile.LOCAL_DEV
    assert resolve_deployment_profile("production") is DeploymentProfile.SELF_HOSTED
    with pytest.raises(ValueError, match="UNKNOWN_DEPLOYMENT_PROFILE"):
        resolve_deployment_profile("cloud_changes_retrieval")


def test_local_profile_preserves_docker_endpoint_compatibility(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DEPLOYMENT_PROFILE", "local_dev")
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://user:password@postgres:5432/rag")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setattr(settings, "MINIO_ENDPOINT", "minio:9000")
    monkeypatch.setattr(settings, "MINIO_ACCESS_KEY", "access")
    monkeypatch.setattr(settings, "MINIO_SECRET_KEY", "secret")
    monkeypatch.setattr(settings, "RECOVERY_CONTROL_DIR", str(tmp_path / "control"))
    result = validate_deployment_configuration()
    assert result.profile == "local_dev"
    assert result.production is False


def test_cloud_profile_requires_external_services_and_e5_artifact(monkeypatch, tmp_path):
    _cloud_settings(monkeypatch, tmp_path)
    result = validate_deployment_configuration()
    assert result.profile == "cloud_control_plane"
    assert result.production is True
    assert "EMBEDDING_MODEL_CACHE_DIR" in result.checks

    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://user:password@postgres:5432/rag")
    with pytest.raises(DeploymentPreflightError, match="CLOUD_PROFILE_LOCAL_ENDPOINT:DATABASE_URL"):
        validate_deployment_configuration(create_control_dir=False)

    _cloud_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "EMBEDDING_MODEL_CACHE_DIR", str(tmp_path / "missing-e5-hub"))
    with pytest.raises(DeploymentPreflightError, match="CANONICAL_E5_ARTIFACT_UNAVAILABLE"):
        validate_deployment_configuration(create_control_dir=False)


def test_cloud_profile_rejects_insecure_object_storage_and_relative_recovery_path(monkeypatch, tmp_path):
    _cloud_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "MINIO_SECURE", False)
    with pytest.raises(DeploymentPreflightError, match="CLOUD_OBJECT_STORAGE_TLS_REQUIRED"):
        validate_deployment_configuration(create_control_dir=False)

    monkeypatch.setattr(settings, "MINIO_SECURE", True)
    monkeypatch.setattr(settings, "BACKUP_DESTINATION", "relative-backups")
    with pytest.raises(DeploymentPreflightError, match="PORTABLE_PATH_REQUIRED:BACKUP_DESTINATION"):
        validate_deployment_configuration(create_control_dir=False)


def test_ollama_endpoint_and_recovery_paths_remain_runtime_configuration(monkeypatch, tmp_path):
    _cloud_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "https://another-generation.example.test")
    monkeypatch.setattr(settings, "RECOVERY_CONTROL_DIR", str(tmp_path / "alternate-control"))
    result = validate_deployment_configuration()
    assert result.profile == "cloud_control_plane"
    assert (tmp_path / "alternate-control").is_dir()


def test_cloud_template_contains_placeholders_not_runtime_secrets():
    template = Path(".env.cloud-control-plane.example").read_text(encoding="utf-8")
    assert "cloud_control_plane" in template
    assert "replace-password" in template
    assert "rag.zkd.id.vn" not in template
    assert "6488c96fa5fa" not in template


def test_embedding_cache_contract_is_the_hugging_face_hub_cache(tmp_path):
    cache = _canonical_e5_cache(tmp_path / "hub")
    snapshot = validate_canonical_e5_artifact(str(cache))
    assert snapshot.parent.parent.name == "models--intfloat--multilingual-e5-base"
    assert snapshot.name == "0123456789abcdef"


def test_unavailable_embedding_artifact_fails_before_model_lookup(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "EMBEDDING_MODEL_CACHE_DIR", str(tmp_path / "missing-hub"))
    called = False

    def unexpected_model(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("model lookup must not run when canonical cache is absent")

    monkeypatch.setattr("app.indexing.embedder.SentenceTransformer", unexpected_model)
    with pytest.raises(CanonicalEmbeddingArtifactError, match="CANONICAL_E5_ARTIFACT_UNAVAILABLE"):
        E5Embedder()
    assert called is False


def test_embedder_passes_the_canonical_hub_cache_without_changing_profile(monkeypatch, tmp_path):
    cache = _canonical_e5_cache(tmp_path / "hub")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL_CACHE_DIR", str(cache))
    monkeypatch.setattr(settings, "EMBEDDING_DEVICE", "cpu")
    captured = {}

    class FakeModel:
        max_seq_length = 512

        class tokenizer:
            is_fast = True

    def fake_model(model_name, **kwargs):
        captured["model_name"] = model_name
        captured.update(kwargs)
        return FakeModel()

    monkeypatch.setattr("app.indexing.embedder.SentenceTransformer", fake_model)
    embedder = E5Embedder()
    assert captured == {
        "model_name": "intfloat/multilingual-e5-base",
        "device": "cpu",
        "cache_folder": str(cache),
        "local_files_only": True,
    }
    assert embedder.embedding_dimension == 768


def test_portable_compose_uses_immutable_app_images_and_no_public_stateful_services():
    compose = Path("deployment/docker-compose.cloud-control-plane.yml").read_text(encoding="utf-8")
    assert "- .:/app" not in compose
    assert "ports:" not in compose
    assert "postgres:" not in compose
    assert "redis:" not in compose
    assert "minio:" not in compose
    assert "EMBEDDING_MODEL_CACHE_HOST_PATH" in compose


def test_cloud_readiness_keeps_generation_transitional(monkeypatch, tmp_path):
    _cloud_settings(monkeypatch, tmp_path)

    class Result:
        def __init__(self, value=None):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class Connection:
        def execute(self, statement):
            text = str(statement)
            if "pg_extension" in text:
                return Result("0.5.1")
            if "alembic_version" in text:
                return Result("head")
            return Result()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class Engine:
        def connect(self):
            return Connection()

    class RedisConnection:
        def ping(self):
            return True

    required = {"ingestion", "document-processing", "document-indexing", "account-deletion", "document-gc"}
    workers = [type("Worker", (), {"queues": [type("Queue", (), {"name": name})()]})() for name in required]
    monkeypatch.setattr("app.deployment.readiness.engine", Engine())
    monkeypatch.setattr("app.deployment.readiness.expected_alembic_head", lambda: "head")
    monkeypatch.setattr("app.deployment.readiness.Redis.from_url", lambda _url: RedisConnection())
    monkeypatch.setattr("app.deployment.readiness.Worker.all", lambda connection: workers)
    monkeypatch.setattr("app.deployment.readiness.minio_client.check_health", lambda: True)
    monkeypatch.setattr("app.deployment.readiness.DeletionTombstoneStore.assert_available", lambda self: None)
    monkeypatch.setattr(
        "app.deployment.readiness.verify_expected_model",
        lambda: pytest.fail("cloud P1 readiness must not require Qwen"),
    )

    from app.deployment.readiness import readiness_report

    report = readiness_report()
    assert report["status"] == "ready"
    assert report["checks"]["model"] == {"ok": True, "required": False, "reason": "P4_GENERATION_TRANSITION"}
