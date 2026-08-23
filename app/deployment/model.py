from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

from app.core.config import settings


class ModelProvisioningError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelIdentity:
    name: str
    digest: str
    size: int | None
    provider_version: str | None


def ollama_version(base_url: str | None = None) -> str | None:
    try:
        response = httpx.get(f"{(base_url or settings.OLLAMA_BASE_URL).rstrip('/')}/api/version", timeout=5)
        response.raise_for_status()
        return response.json().get("version")
    except Exception:
        return None


def find_model_identity(model: str | None = None, base_url: str | None = None) -> ModelIdentity | None:
    expected = model or settings.GENERATION_MODEL_ID
    try:
        response = httpx.get(f"{(base_url or settings.OLLAMA_BASE_URL).rstrip('/')}/api/tags", timeout=5)
        response.raise_for_status()
        for item in response.json().get("models", []):
            name = item.get("name") or item.get("model")
            if name == expected or name == f"{expected}:latest":
                return ModelIdentity(
                    name=name,
                    digest=str(item.get("digest") or ""),
                    size=item.get("size"),
                    provider_version=ollama_version(base_url),
                )
        return None
    except Exception as exc:
        raise ModelProvisioningError("MODEL_PROVIDER_UNAVAILABLE") from exc


def verify_expected_model() -> ModelIdentity:
    identity = find_model_identity()
    if identity is None:
        raise ModelProvisioningError("MODEL_NOT_PROVISIONED")
    expected_digest = settings.EXPECTED_MODEL_DIGEST.strip()
    if expected_digest and identity.digest != expected_digest:
        raise ModelProvisioningError("MODEL_DIGEST_MISMATCH")
    if not identity.digest:
        raise ModelProvisioningError("MODEL_DIGEST_UNAVAILABLE")
    return identity


def provision_online(model: str, *, allow_network: bool, output: Path) -> ModelIdentity:
    if not allow_network:
        raise ModelProvisioningError("ONLINE_MODEL_PROVISIONING_REQUIRES_EXPLICIT_NETWORK_ACK")
    if shutil.which("ollama") is None:
        raise ModelProvisioningError("OLLAMA_CLI_NOT_AVAILABLE")
    subprocess.run(["ollama", "pull", model], check=True)
    identity = find_model_identity(model)
    if identity is None:
        raise ModelProvisioningError("MODEL_NOT_PROVISIONED")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(identity), indent=2, sort_keys=True), encoding="utf-8")
    return identity


def verify_offline_store(source: Path, expected_sha256: str) -> str:
    if not source.is_file():
        raise ModelProvisioningError("OFFLINE_MODEL_ARTIFACT_MISSING")
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    actual = digest.hexdigest()
    if actual != expected_sha256.casefold():
        raise ModelProvisioningError("OFFLINE_MODEL_ARTIFACT_HASH_MISMATCH")
    return actual
