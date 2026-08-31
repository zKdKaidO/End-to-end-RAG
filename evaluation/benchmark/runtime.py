"""Hard target checks shared by benchmark-only tooling."""

from urllib.parse import urlparse

from app.core.config import DeploymentProfile, settings


class BenchmarkTargetError(RuntimeError):
    pass


def _host(value: str, *, url: bool) -> str:
    parsed = urlparse(value if url else f"//{value}")
    return (parsed.hostname or "").casefold()


def assert_benchmark_runtime() -> None:
    if settings.resolved_deployment_profile() is not DeploymentProfile.BENCHMARK:
        raise BenchmarkTargetError("BENCHMARK_PROFILE_REQUIRED")
    if settings.BENCHMARK_RUNTIME_MARKER != "rag-benchmark-v1":
        raise BenchmarkTargetError("BENCHMARK_RUNTIME_MARKER_INVALID")
    if _host(settings.DATABASE_URL, url=True) != "benchmark-postgres" or urlparse(settings.DATABASE_URL).path.lstrip("/") != "rag_benchmark":
        raise BenchmarkTargetError("BENCHMARK_DATABASE_TARGET_INVALID")
    if _host(settings.REDIS_URL, url=True) != "benchmark-redis":
        raise BenchmarkTargetError("BENCHMARK_REDIS_TARGET_INVALID")
    if _host(settings.MINIO_ENDPOINT, url=False) != "benchmark-minio" or settings.MINIO_BUCKET != "benchmark-documents":
        raise BenchmarkTargetError("BENCHMARK_OBJECT_STORAGE_TARGET_INVALID")
