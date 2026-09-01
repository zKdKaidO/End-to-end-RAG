"""Small executable loopback listener for the isolated control service."""

from __future__ import annotations

import socket
import threading
import time

import uvicorn

from .api import create_local_compute_app
from .runtime import LocalComputeRuntime


class LoopbackControlServer:
    """Owns a literal-loopback ephemeral listener and graceful stop boundary."""

    def __init__(self, runtime: LocalComputeRuntime):
        self.runtime = runtime
        self.listener: socket.socket | None = None
        self.server: uvicorn.Server | None = None
        self.thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        if not self.runtime.bound_port:
            raise RuntimeError("LOCAL_COMPUTE_NOT_STARTED")
        return self.runtime.bound_port

    def start(self) -> None:
        self.listener = self.runtime.bind_ephemeral_socket()
        self.server = uvicorn.Server(uvicorn.Config(create_local_compute_app(self.runtime), log_level="critical", access_log=False))
        self.thread = threading.Thread(target=self.server.run, kwargs={"sockets": [self.listener]}, daemon=True)
        self.thread.start()
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.05):
                    return
            except OSError:
                time.sleep(0.01)
        self.stop()
        raise RuntimeError("LOCAL_COMPUTE_LISTENER_START_FAILED")

    def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
        if self.thread is not None:
            self.thread.join(timeout=3)
        if self.listener is not None:
            try:
                self.listener.close()
            except OSError:
                pass
