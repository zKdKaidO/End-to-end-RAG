from __future__ import annotations

from pathlib import Path

import pytest

from app.indexing.artifact import (
    CanonicalEmbeddingArtifactError,
    validate_canonical_e5_artifact,
)
from app.indexing import input_contract
from app.local_compute.model_cache import resolve_huggingface_hub_cache
from app.local_compute.settings import LocalComputeSettings


def _canonical_cache(root: Path, revision: str = "abcdef012345") -> Path:
    snapshot = (
        root
        / "models--intfloat--multilingual-e5-base"
        / "snapshots"
        / revision
    )
    snapshot.mkdir(parents=True)
    ref = snapshot.parent.parent / "refs"
    ref.mkdir()
    (ref / "main").write_text(revision, encoding="utf-8")
    for name in ("config.json", "modules.json", "model.safetensors", "tokenizer_config.json"):
        (snapshot / name).write_text("{}", encoding="utf-8")
    return root


def test_resolver_honors_standard_hub_variables_without_linux_default(tmp_path):
    explicit = tmp_path / "explicit-hub"
    resolved = resolve_huggingface_hub_cache(
        environment={"HF_HUB_CACHE": str(explicit)}, home=Path("/root")
    )
    assert resolved == explicit
    assert str(resolved) != "/root/.cache/huggingface/hub"


def test_resolver_uses_hf_home_then_windows_safe_default(tmp_path):
    assert resolve_huggingface_hub_cache(
        environment={"HF_HOME": str(tmp_path / "hf-home")}
    ) == tmp_path / "hf-home" / "hub"
    fallback = resolve_huggingface_hub_cache(environment={}, home=tmp_path / "User")
    assert fallback == tmp_path / "User" / ".cache" / "huggingface" / "hub"


def test_local_settings_explicit_cache_wins_over_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "other"))
    configured = tmp_path / "canonical-hub"
    settings = LocalComputeSettings(
        data_root=tmp_path / "Compute",
        development_mode=True,
        embedding_model_cache_dir=configured,
    )
    assert settings.embedding_model_cache_dir == configured


def test_artifact_validator_distinguishes_wrong_root_and_missing_snapshot(tmp_path):
    hub = _canonical_cache(tmp_path / "hf-home" / "hub")
    with pytest.raises(CanonicalEmbeddingArtifactError, match="wrong_cache_root"):
        validate_canonical_e5_artifact(str(hub.parent))

    root = tmp_path / "missing-snapshot"
    model = root / "models--intfloat--multilingual-e5-base"
    (model / "refs").mkdir(parents=True)
    (model / "refs" / "main").write_text("abcdef", encoding="utf-8")
    with pytest.raises(CanonicalEmbeddingArtifactError, match="missing_snapshot"):
        validate_canonical_e5_artifact(str(root))


def test_tokenizer_loader_uses_explicit_cache_offline(monkeypatch, tmp_path):
    captured = {}

    class Tokenizer:
        is_fast = True
        model_max_length = 512

    def load(model_id, **kwargs):
        captured["model_id"] = model_id
        captured.update(kwargs)
        return Tokenizer()

    input_contract.get_e5_input_contract.cache_clear()
    monkeypatch.setattr(input_contract.AutoTokenizer, "from_pretrained", load)
    cache = tmp_path / "hub"
    contract = input_contract.get_e5_input_contract(str(cache))
    assert contract.tokenizer.is_fast
    assert captured == {
        "model_id": "intfloat/multilingual-e5-base",
        "cache_dir": str(cache),
        "local_files_only": True,
        "use_fast": True,
    }
    input_contract.get_e5_input_contract.cache_clear()
