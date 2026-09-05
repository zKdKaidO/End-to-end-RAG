"""Product paths and packaged-resource lookup for Windows ZKD Compute.

This module is deliberately free of RAG imports so the launcher can configure
the managed model cache before transformers or sentence-transformers load.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .model_cache import resolve_huggingface_hub_cache
from .settings import default_data_root


def product_data_root() -> Path:
    """Return the per-user persistent root, with a test/support override."""
    configured = os.environ.get("ZKD_COMPUTE_DATA_ROOT")
    return Path(configured).expanduser().resolve() if configured else default_data_root()


def packaged_resource_root() -> Path:
    """Find bundled application resources in source and PyInstaller modes."""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root)
    return Path(__file__).resolve().parents[2]


def resource_path(*parts: str) -> Path:
    return packaged_resource_root().joinpath(*parts)


def local_model_cache_path() -> Path:
    """Return the standard local HF hub cache without mutating process env."""
    return resolve_huggingface_hub_cache()
