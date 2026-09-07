from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.local_compute.deployment_profile import ComputeDeploymentProfile, PRODUCTION_PROFILE, STAGING_GRANT_PUBLIC_KEY, STAGING_PROFILE, get_profile, provision_staging_public_key
from app.local_compute.grants import PlatformGrantVerificationKeyProvider, _verify_grant_signature


def test_production_is_default_and_staging_isolated(monkeypatch, tmp_path):
    monkeypatch.delenv("ZKD_COMPUTE_DATA_ROOT", raising=False)
    assert get_profile().name is ComputeDeploymentProfile.PRODUCTION
    assert PRODUCTION_PROFILE.platform_origin == "https://rag.zkd.id.vn"
    assert STAGING_PROFILE.platform_origin == "https://zkd-control-plane-staging.zkd-rag.workers.dev"
    assert STAGING_PROFILE.data_root().name == "Compute-Staging"
    assert PRODUCTION_PROFILE.mutex_name != STAGING_PROFILE.mutex_name
    monkeypatch.setenv("ZKD_COMPUTE_DATA_ROOT", str(tmp_path / "isolated"))
    assert STAGING_PROFILE.data_root() == tmp_path / "isolated"


def test_only_staging_provisions_the_provided_public_key(monkeypatch, tmp_path):
    monkeypatch.setenv("ZKD_COMPUTE_DATA_ROOT", str(tmp_path / "Compute-Staging"))
    path = provision_staging_public_key(STAGING_PROFILE)
    assert path.read_text(encoding="utf-8").strip() == STAGING_GRANT_PUBLIC_KEY
    with pytest.raises(ValueError):
        provision_staging_public_key(PRODUCTION_PROFILE)


def test_ephemeral_grant_key_rejects_bad_signature():
    key = Ed25519PrivateKey.generate()
    public = base64.b64encode(key.public_key().public_bytes_raw()).decode("ascii")
    provider = PlatformGrantVerificationKeyProvider(public)
    with pytest.raises(Exception):
        _verify_grant_signature("not.a.signature", provider)
