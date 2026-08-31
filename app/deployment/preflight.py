from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from app.core.config import DeploymentProfile, resolve_deployment_profile, settings
from app.indexing.artifact import CanonicalEmbeddingArtifactError, validate_canonical_e5_artifact


class DeploymentPreflightError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreflightResult:
    profile: str
    production: bool
    checks: tuple[str, ...]


_LOCAL_ONLY_HOSTS = {
    "localhost", "127.0.0.1", "::1", "host.docker.internal",
    "postgres", "redis", "minio", "ollama",
}


def _endpoint_host(value: str, *, url: bool) -> str:
    parsed = urlparse(value if url else f"//{value}")
    return (parsed.hostname or "").casefold()


def _require_external_endpoint(name: str, value: str, *, url: bool) -> None:
    host = _endpoint_host(value, url=url)
    if not host or host in _LOCAL_ONLY_HOSTS:
        raise DeploymentPreflightError(f"CLOUD_PROFILE_LOCAL_ENDPOINT:{name}")


def _require_absolute_path(name: str, value: str) -> Path:
    if not value.strip() or not Path(value).is_absolute():
        raise DeploymentPreflightError(f"PORTABLE_PATH_REQUIRED:{name}")
    return Path(value)


def validate_deployment_configuration(*, create_control_dir: bool = True) -> PreflightResult:
    try:
        resolved_profile = resolve_deployment_profile(settings.DEPLOYMENT_PROFILE)
    except ValueError as exc:
        raise DeploymentPreflightError(str(exc)) from exc
    profile = resolved_profile.value
    production = resolved_profile in {DeploymentProfile.SELF_HOSTED, DeploymentProfile.CLOUD_CONTROL_PLANE}
    checks: list[str] = []

    for name in ("DATABASE_URL", "REDIS_URL", "MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY"):
        if not str(getattr(settings, name, "")).strip():
            raise DeploymentPreflightError(f"REQUIRED_CONFIGURATION_MISSING:{name}")
        checks.append(name)

    database = urlparse(settings.DATABASE_URL)
    if not database.password:
        raise DeploymentPreflightError("REQUIRED_CONFIGURATION_MISSING:DATABASE_PASSWORD")

    control_dir = Path(settings.RECOVERY_CONTROL_DIR).resolve()
    if create_control_dir:
        control_dir.mkdir(parents=True, exist_ok=True)
        probe = control_dir / f".write-probe-{uuid4().hex}"
        try:
            probe.write_text("deployment-v1", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            raise DeploymentPreflightError("RECOVERY_CONTROL_STORE_UNWRITABLE") from exc
    checks.append("RECOVERY_CONTROL_DIR")

    if resolved_profile in {
        DeploymentProfile.PC_TUNNEL,
        DeploymentProfile.SELF_HOSTED,
        DeploymentProfile.CLOUD_CONTROL_PLANE,
    }:
        if not settings.AUTH_COOKIE_SECURE:
            raise DeploymentPreflightError("INSECURE_PRODUCTION_COOKIE")
        if not settings.SECURITY_HSTS_ENABLED:
            raise DeploymentPreflightError("PRODUCTION_HSTS_NOT_ENABLED")
        origins = [item.strip() for item in settings.AUTH_TRUSTED_ORIGINS.split(",") if item.strip()]
        if not origins or any(not origin.startswith("https://") for origin in origins):
            raise DeploymentPreflightError("INSECURE_PRODUCTION_TRUSTED_ORIGIN")

        checks.extend(("AUTH_COOKIE_SECURE", "SECURITY_HSTS_ENABLED", "AUTH_TRUSTED_ORIGINS"))

    if resolved_profile in {DeploymentProfile.SELF_HOSTED, DeploymentProfile.CLOUD_CONTROL_PLANE}:
        if not settings.TRUSTED_PROXY_CIDRS.strip():
            raise DeploymentPreflightError("TRUSTED_PROXY_CONFIGURATION_MISSING")
        if not settings.RELEASE_ID.strip() or settings.RELEASE_ID == "development":
            raise DeploymentPreflightError("RELEASE_ID_MISSING")
        if resolved_profile is not DeploymentProfile.CLOUD_CONTROL_PLANE and not settings.EXPECTED_MODEL_DIGEST.strip():
            raise DeploymentPreflightError("EXPECTED_MODEL_DIGEST_MISSING")
        if not settings.BACKUP_DESTINATION.strip():
            raise DeploymentPreflightError("BACKUP_DESTINATION_MISSING")
        if not settings.BACKUP_DESTINATION_ENCRYPTED:
            raise DeploymentPreflightError("BACKUP_DESTINATION_ENCRYPTION_REQUIRED")
        if not settings.BACKUP_DESTINATION_SEPARATE_FAILURE_DOMAIN:
            raise DeploymentPreflightError("BACKUP_SEPARATE_FAILURE_DOMAIN_REQUIRED")
        checks.extend((
            "TRUSTED_PROXY_CIDRS", "RELEASE_ID",
            "BACKUP_DESTINATION_ENCRYPTED", "BACKUP_DESTINATION_SEPARATE_FAILURE_DOMAIN",
        ))
        if resolved_profile is not DeploymentProfile.CLOUD_CONTROL_PLANE:
            checks.append("EXPECTED_MODEL_DIGEST")

    if resolved_profile is DeploymentProfile.CLOUD_CONTROL_PLANE:
        _require_external_endpoint("DATABASE_URL", settings.DATABASE_URL, url=True)
        _require_external_endpoint("REDIS_URL", settings.REDIS_URL, url=True)
        _require_external_endpoint("MINIO_ENDPOINT", settings.MINIO_ENDPOINT, url=False)
        _require_external_endpoint("OLLAMA_BASE_URL", settings.OLLAMA_BASE_URL, url=True)
        if not settings.MINIO_SECURE:
            raise DeploymentPreflightError("CLOUD_OBJECT_STORAGE_TLS_REQUIRED")
        _require_absolute_path("RECOVERY_CONTROL_DIR", settings.RECOVERY_CONTROL_DIR)
        _require_absolute_path("BACKUP_DESTINATION", settings.BACKUP_DESTINATION)
        _require_absolute_path("EMBEDDING_MODEL_CACHE_DIR", settings.EMBEDDING_MODEL_CACHE_DIR)
        try:
            validate_canonical_e5_artifact(settings.EMBEDDING_MODEL_CACHE_DIR)
        except CanonicalEmbeddingArtifactError as exc:
            raise DeploymentPreflightError(str(exc)) from exc
        checks.extend((
            "EXTERNAL_DATABASE_URL", "EXTERNAL_REDIS_URL", "EXTERNAL_OBJECT_STORAGE",
            "EXTERNAL_GENERATION_ENDPOINT", "EMBEDDING_MODEL_CACHE_DIR",
        ))

    if settings.BACKUP_RETENTION_DAYS < 0 or settings.BACKUP_KEEP_LAST < 0:
        raise DeploymentPreflightError("INVALID_BACKUP_RETENTION")
    if settings.RESTORE_MAX_PARALLEL_MAINTENANCE_WORKERS < 0:
        raise DeploymentPreflightError("INVALID_RESTORE_WORKER_LIMIT")

    return PreflightResult(profile=profile, production=production, checks=tuple(checks))
