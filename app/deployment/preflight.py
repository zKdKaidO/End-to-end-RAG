from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from app.core.config import settings


class DeploymentPreflightError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreflightResult:
    profile: str
    production: bool
    checks: tuple[str, ...]


def validate_deployment_configuration(*, create_control_dir: bool = True) -> PreflightResult:
    profile = settings.DEPLOYMENT_PROFILE.strip().casefold()
    production = profile == "production"
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

    if production:
        if not settings.AUTH_COOKIE_SECURE:
            raise DeploymentPreflightError("INSECURE_PRODUCTION_COOKIE")
        if not settings.SECURITY_HSTS_ENABLED:
            raise DeploymentPreflightError("PRODUCTION_HSTS_NOT_ENABLED")
        origins = [item.strip() for item in settings.AUTH_TRUSTED_ORIGINS.split(",") if item.strip()]
        if not origins or any(not origin.startswith("https://") for origin in origins):
            raise DeploymentPreflightError("INSECURE_PRODUCTION_TRUSTED_ORIGIN")
        if not settings.TRUSTED_PROXY_CIDRS.strip():
            raise DeploymentPreflightError("TRUSTED_PROXY_CONFIGURATION_MISSING")
        if not settings.RELEASE_ID.strip() or settings.RELEASE_ID == "development":
            raise DeploymentPreflightError("RELEASE_ID_MISSING")
        if not settings.EXPECTED_MODEL_DIGEST.strip():
            raise DeploymentPreflightError("EXPECTED_MODEL_DIGEST_MISSING")
        if not settings.BACKUP_DESTINATION.strip():
            raise DeploymentPreflightError("BACKUP_DESTINATION_MISSING")
        if not settings.BACKUP_DESTINATION_ENCRYPTED:
            raise DeploymentPreflightError("BACKUP_DESTINATION_ENCRYPTION_REQUIRED")
        if not settings.BACKUP_DESTINATION_SEPARATE_FAILURE_DOMAIN:
            raise DeploymentPreflightError("BACKUP_SEPARATE_FAILURE_DOMAIN_REQUIRED")
        checks.extend((
            "AUTH_COOKIE_SECURE", "SECURITY_HSTS_ENABLED", "AUTH_TRUSTED_ORIGINS",
            "TRUSTED_PROXY_CIDRS", "RELEASE_ID", "EXPECTED_MODEL_DIGEST",
            "BACKUP_DESTINATION_ENCRYPTED", "BACKUP_DESTINATION_SEPARATE_FAILURE_DOMAIN",
        ))

    if settings.BACKUP_RETENTION_DAYS < 0 or settings.BACKUP_KEEP_LAST < 0:
        raise DeploymentPreflightError("INVALID_BACKUP_RETENTION")
    if settings.RESTORE_MAX_PARALLEL_MAINTENANCE_WORKERS < 0:
        raise DeploymentPreflightError("INVALID_RESTORE_WORKER_LIMIT")

    return PreflightResult(profile=profile, production=production, checks=tuple(checks))
