"""Verified local model/runtime provisioning boundaries.

No binary URL or checksum is invented here. Release engineering supplies a
versioned manifest before a model/runtime can be downloaded or executed.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from app.indexing.artifact import CanonicalEmbeddingArtifactError, validate_canonical_e5_artifact
from app.indexing.input_contract import EMBEDDING_MODEL_NAME

from .errors import LocalComputeError, LocalComputeErrorCode


@dataclass(frozen=True)
class ProvisionedAsset:
    name: str
    version: str
    url: str
    sha256: str

    def validate(self) -> None:
        if not self.url.startswith("https://") or len(self.sha256) != 64 or any(char not in "0123456789abcdef" for char in self.sha256.casefold()):
            raise ValueError("ZKD_COMPUTE_PROVISIONING_MANIFEST_INVALID")


class E5ModelProvisioner:
    model_id = EMBEDDING_MODEL_NAME

    def __init__(self, cache_dir: Path, asset: ProvisionedAsset | None = None) -> None:
        self.cache_dir, self.asset = cache_dir, asset

    def is_ready(self) -> bool:
        try:
            validate_canonical_e5_artifact(str(self.cache_dir))
            return True
        except CanonicalEmbeddingArtifactError:
            return False

    def require_ready(self) -> Path:
        try:
            return validate_canonical_e5_artifact(str(self.cache_dir))
        except CanonicalEmbeddingArtifactError as exc:
            raise LocalComputeError(LocalComputeErrorCode.MODEL_ARTIFACT_UNAVAILABLE, "The required local embedding model is not provisioned.") from exc

    def provision(self, *, allow_download: bool = False) -> Path:
        if self.is_ready():
            return self.require_ready()
        if not allow_download or self.asset is None:
            raise LocalComputeError(LocalComputeErrorCode.MODEL_ARTIFACT_UNAVAILABLE, "Model provisioning is required before local indexing.")
        self.asset.validate()
        # A release-provided archive is the only accepted download shape.
        target = self.cache_dir.parent / "downloads" / f"{self.asset.name}-{self.asset.version}.archive"
        target.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(self.asset.url, timeout=120) as response, target.open("wb") as output:
            digest = hashlib.sha256()
            for block in iter(lambda: response.read(1024 * 1024), b""):
                digest.update(block); output.write(block)
        if digest.hexdigest() != self.asset.sha256:
            target.unlink(missing_ok=True)
            raise LocalComputeError(LocalComputeErrorCode.MODEL_ARTIFACT_UNAVAILABLE, "Downloaded model verification failed.")
        raise LocalComputeError(LocalComputeErrorCode.MODEL_ARTIFACT_UNAVAILABLE, "Verified archive extraction is release-pipeline owned.")


class GenerationRuntimeManager:
    """Lifecycle boundary for a release-bundled Ollama-compatible sidecar."""

    def __init__(self, runtime_dir: Path, *, executable: Path | None = None, expected_sha256: str | None = None) -> None:
        self.runtime_dir, self.executable, self.expected_sha256 = runtime_dir, executable, expected_sha256
        self.process: subprocess.Popen | None = None

    def _verified_executable(self) -> Path:
        if self.executable is None or not self.executable.is_file() or not self.expected_sha256:
            raise LocalComputeError(LocalComputeErrorCode.GENERATION_UNAVAILABLE, "Local generation runtime is not provisioned.")
        digest = hashlib.sha256(self.executable.read_bytes()).hexdigest()
        if digest != self.expected_sha256:
            raise LocalComputeError(LocalComputeErrorCode.GENERATION_UNAVAILABLE, "Local generation runtime verification failed.")
        return self.executable

    def start(self) -> None:
        if self.process and self.process.poll() is None:
            return
        executable = self._verified_executable()
        environment = {**os.environ, "OLLAMA_HOST": "127.0.0.1:11434"}
        self.process = subprocess.Popen([str(executable), "serve"], cwd=str(self.runtime_dir), env=environment, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None
