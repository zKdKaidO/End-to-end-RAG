"""Canonical deployment profiles for the installed local Compute runtime.

Profiles separate trust roots and durable device state.  They are intentionally
small: profile selection never changes local document/RAG behaviour.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .settings import PRODUCT_ORIGIN, default_data_root


STAGING_ORIGIN = "https://zkd-control-plane-staging.zkd-rag.workers.dev"
STAGING_GRANT_PUBLIC_KEY = "E3k/VqWnBvaK9o+0jB/6Qom0Gk3GNCNYzrHseOkS2m8="


class ComputeDeploymentProfile(str, Enum):
    PRODUCTION = "production"
    STAGING = "staging"


@dataclass(frozen=True)
class DeploymentProfile:
    name: ComputeDeploymentProfile
    platform_origin: str
    mutex_name: str
    tray_prefix: str

    def data_root(self) -> Path:
        # Explicit override is a test/support facility. It never redirects the
        # installed production app unless an operator explicitly supplies it.
        override = os.environ.get("ZKD_COMPUTE_DATA_ROOT")
        if override:
            return Path(override).expanduser().resolve()
        root = default_data_root()
        return root if self.name is ComputeDeploymentProfile.PRODUCTION else root.with_name("Compute-Staging")

    @property
    def public_key_path(self) -> Path:
        return self.data_root() / "config" / "platform-grant-public.b64"

    @property
    def is_staging(self) -> bool:
        return self.name is ComputeDeploymentProfile.STAGING


PRODUCTION_PROFILE = DeploymentProfile(ComputeDeploymentProfile.PRODUCTION, PRODUCT_ORIGIN, "Local\\ZKD.Compute.Runtime.V1", "ZKD Compute")
STAGING_PROFILE = DeploymentProfile(ComputeDeploymentProfile.STAGING, STAGING_ORIGIN, "Local\\ZKD.Compute.Staging.Runtime.V1", "ZKD Compute [STAGING]")


def get_profile(value: str | ComputeDeploymentProfile = ComputeDeploymentProfile.PRODUCTION) -> DeploymentProfile:
    profile = ComputeDeploymentProfile(value)
    return STAGING_PROFILE if profile is ComputeDeploymentProfile.STAGING else PRODUCTION_PROFILE


def provision_staging_public_key(profile: DeploymentProfile) -> Path:
    """Create only the isolated staging verifier file; never touch production."""
    if not profile.is_staging:
        raise ValueError("STAGING_PROFILE_REQUIRED")
    path = profile.public_key_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(STAGING_GRANT_PUBLIC_KEY + "\n", encoding="utf-8")
    return path
