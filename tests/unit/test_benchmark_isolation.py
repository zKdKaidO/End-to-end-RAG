import pytest

from app.core.config import DeploymentProfile, resolve_deployment_profile, settings
from app.deployment.preflight import DeploymentPreflightError, validate_deployment_configuration
from evaluation.benchmark.runtime import BenchmarkTargetError, assert_benchmark_runtime
from evaluation.benchmark.fixture import load_fixture


def _benchmark_settings(monkeypatch, tmp_path):
    values = {
        "DEPLOYMENT_PROFILE": "benchmark", "BENCHMARK_RUNTIME_MARKER": "rag-benchmark-v1",
        "DATABASE_URL": "postgresql://benchmark:password@benchmark-postgres:5432/rag_benchmark",
        "REDIS_URL": "redis://benchmark-redis:6379/0", "MINIO_ENDPOINT": "benchmark-minio:9000",
        "MINIO_ACCESS_KEY": "access", "MINIO_SECRET_KEY": "secret", "MINIO_BUCKET": "benchmark-documents",
        "RECOVERY_CONTROL_DIR": str(tmp_path / "control"),
    }
    for name, value in values.items():
        monkeypatch.setattr(settings, name, value)


def test_benchmark_profile_is_explicit_and_targeted(monkeypatch, tmp_path):
    _benchmark_settings(monkeypatch, tmp_path)
    assert resolve_deployment_profile("benchmark") is DeploymentProfile.BENCHMARK
    assert_benchmark_runtime()
    assert validate_deployment_configuration().profile == "benchmark"


@pytest.mark.parametrize("name,value,error,preflight_error", [
    ("DATABASE_URL", "postgresql://benchmark:password@postgres:5432/rag_benchmark", "DATABASE", "DATABASE"),
    ("REDIS_URL", "redis://redis:6379/0", "REDIS", "REDIS"),
    ("MINIO_BUCKET", "documents", "OBJECT_STORAGE", "BUCKET"),
])
def test_benchmark_runtime_rejects_normal_service_targets(monkeypatch, tmp_path, name, value, error, preflight_error):
    _benchmark_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, name, value)
    with pytest.raises(BenchmarkTargetError, match=error):
        assert_benchmark_runtime()
    with pytest.raises(DeploymentPreflightError, match=preflight_error):
        validate_deployment_configuration(create_control_dir=False)


def test_large_frozen_fixture_preserves_representative_retrieval_inputs():
    fixture = load_fixture()
    assert fixture["fixture_version"] == "legal-retrieval-v2"
    assert len(fixture["documents"]) == 44
    assert len(fixture["chunks"]) == len(fixture["chunk_indexes"]) == 613
    assert len(fixture["objects"]) == 18
    assert {row["embedding_dimension"] for row in fixture["chunk_indexes"]} == {768}
