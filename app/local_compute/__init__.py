"""Isolated ZKD Compute control-runtime foundation.

This package deliberately owns no production RAG workload.  It is the
loopback control boundary that later local document preparation can use.
"""

from .runtime import LocalComputeRuntime
from .settings import LocalComputeSettings

__all__ = ["LocalComputeRuntime", "LocalComputeSettings"]
