"""Development-only executable control-service entry point; no RAG workloads."""

from __future__ import annotations

import argparse
from pathlib import Path

from .runtime import LocalComputeRuntime
from .server import LoopbackControlServer
from .settings import LocalComputeSettings


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the isolated ZKD Compute control skeleton.")
    parser.add_argument("--data-root")
    parser.add_argument("--development", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    arguments = parser.parse_args()
    settings = LocalComputeSettings(
        data_root=LocalComputeSettings().data_root if not arguments.data_root else Path(arguments.data_root),
        bind_port=arguments.port,
        development_mode=arguments.development,
        development_origins=("http://localhost:5173",) if arguments.development else (),
    )
    runtime = LocalComputeRuntime(settings)
    runtime.start()
    try:
        server = LoopbackControlServer(runtime)
        server.start()
        # The executable service is intentionally quiet and does not expose
        # its endpoint through a public interface. Packaging later owns
        # authenticated endpoint discovery.
        if server.thread is not None:
            server.thread.join()
    finally:
        runtime.shutdown()


if __name__ == "__main__":
    main()
