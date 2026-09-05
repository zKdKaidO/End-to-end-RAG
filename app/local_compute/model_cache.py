"""Desktop-safe Hugging Face hub-cache resolution.

This module intentionally has no dependency on the server Settings object.  A
local Compute process can therefore discover an already installed canonical
artifact without inheriting Docker's ``/root`` cache path or mutating the
process-wide Hugging Face environment.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


_HUB_ENV_NAMES = ("HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE")


def resolve_huggingface_hub_cache(
    *,
    environment: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Resolve the standard Hugging Face *hub* directory without downloads.

    An explicit ``LocalComputeSettings.embedding_model_cache_dir`` takes
    precedence over this function.  Otherwise this follows Hugging Face's
    documented hub-cache variables, then ``HF_HOME/hub``, then the normal
    per-user Windows/Linux convention.  It deliberately returns a path only;
    canonical artifact validation remains a separate fail-closed operation.
    """

    values = os.environ if environment is None else environment
    for name in _HUB_ENV_NAMES:
        configured = values.get(name)
        if configured:
            return Path(configured).expanduser()

    hf_home = values.get("HF_HOME")
    if hf_home:
        return Path(hf_home).expanduser() / "hub"

    user_home = home or Path.home()
    return user_home / ".cache" / "huggingface" / "hub"
