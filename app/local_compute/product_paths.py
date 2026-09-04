"""Product paths and packaged-resource lookup for Windows ZKD Compute.

This module is deliberately free of RAG imports so the launcher can configure
the managed model cache before transformers or sentence-transformers load.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

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


def configure_managed_model_environment(data_root: Path | None = None) -> Path:
    """Set process-local HF locations before any ML package is imported.

    ``EMBEDDING_MODEL_CACHE_DIR`` is retained because frozen E5 code consumes
    it, but is set by the product rather than requested from a user.
    """
    root = data_root or product_data_root()
    cache = root / "models" / "huggingface"
    home = root / "models" / "huggingface-home"
    cache.mkdir(parents=True, exist_ok=True)
    home.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(home)
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(cache)
    os.environ["TRANSFORMERS_CACHE"] = str(cache)
    os.environ["EMBEDDING_MODEL_CACHE_DIR"] = str(cache)
    # A few frozen shared RAG modules currently read the monolithic server
    # Settings object for limits/profile defaults. They do not contact these
    # services in local Compute, but Settings must be constructible without a
    # user creating a server .env file. These are process-local inert values,
    # set before that module is imported; no local Compute code uses them.
    os.environ["ZKD_COMPUTE_PRODUCT_MODE"] = "1"
    os.environ.setdefault("DATABASE_URL", "sqlite:///zkd-compute-unused.db")
    os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:0/0")
    os.environ.setdefault("MINIO_ENDPOINT", "127.0.0.1:0")
    os.environ.setdefault("MINIO_ACCESS_KEY", "local-compute-unused")
    os.environ.setdefault("MINIO_SECRET_KEY", "local-compute-unused")
    os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    return cache
