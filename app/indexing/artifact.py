"""Validation for the deployment-provisioned canonical E5 artifact."""

from __future__ import annotations

from pathlib import Path

from app.indexing.input_contract import EMBEDDING_MODEL_NAME


class CanonicalEmbeddingArtifactError(RuntimeError):
    pass


_MODEL_CACHE_DIRECTORY = "models--" + EMBEDDING_MODEL_NAME.replace("/", "--")
_REQUIRED_SNAPSHOT_FILES = (
    "config.json",
    "modules.json",
    "model.safetensors",
    "tokenizer_config.json",
)


def validate_canonical_e5_artifact(cache_dir: str) -> Path:
    """Return the canonical cached snapshot or fail before any network lookup.

    ``cache_dir`` is the Hugging Face *hub cache* directory: it directly
    contains ``models--intfloat--multilingual-e5-base``. It is deliberately
    not the Hugging Face home directory that contains a nested ``hub`` folder.
    """

    root = Path(cache_dir)
    model_root = root / _MODEL_CACHE_DIRECTORY
    ref = model_root / "refs" / "main"
    if not ref.is_file():
        raise CanonicalEmbeddingArtifactError("CANONICAL_E5_ARTIFACT_UNAVAILABLE:missing_ref")

    revision = ref.read_text(encoding="utf-8").strip()
    if not revision or "/" in revision or "\\" in revision:
        raise CanonicalEmbeddingArtifactError("CANONICAL_E5_ARTIFACT_UNAVAILABLE:invalid_ref")

    snapshot = model_root / "snapshots" / revision
    for filename in _REQUIRED_SNAPSHOT_FILES:
        if not (snapshot / filename).is_file():
            raise CanonicalEmbeddingArtifactError(
                f"CANONICAL_E5_ARTIFACT_UNAVAILABLE:missing_{filename}"
            )
    return snapshot
