"""Small executable loopback listener for the isolated control service."""

from __future__ import annotations

import socket
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable

import uvicorn

from .api import create_local_compute_app
from .runtime import LocalComputeRuntime


class LoopbackControlServer:
    """Owns a literal-loopback ephemeral listener and graceful stop boundary."""

    def __init__(
        self,
        runtime: LocalComputeRuntime,
        failure_reporter: Callable[[str, BaseException], None] | None = None,
    ):
        self.runtime = runtime
        self.failure_reporter = failure_reporter
        self.listener: socket.socket | None = None
        self.server: uvicorn.Server | None = None
        self.thread: threading.Thread | None = None
        self.startup_error: BaseException | None = None

    @property
    def port(self) -> int:
        if not self.runtime.bound_port:
            raise RuntimeError("LOCAL_COMPUTE_NOT_STARTED")
        return self.runtime.bound_port

    def start(self) -> None:
        if self.thread is not None and self.thread.is_alive():
            raise RuntimeError("LOCAL_COMPUTE_LISTENER_ALREADY_RUNNING")

        self.startup_error = None
        self.listener = self.runtime.bind_ephemeral_socket()

        try:
            app = create_local_compute_app(self.runtime)
            self.server = uvicorn.Server(
                uvicorn.Config(
                    app,
                    log_level="critical",
                    access_log=False,
                    # The windowed PyInstaller bootloader sets stderr to
                    # None. Uvicorn's default formatter probes that stream
                    # during logging configuration and can fail before the
                    # listener starts. Bootstrap diagnostics are owned by the
                    # launcher, so this control server intentionally supplies
                    # no Uvicorn logging configuration.
                    log_config=None,
                )
            )
            self.thread = threading.Thread(
                target=self._serve,
                name="zkd-loopback-control",
                daemon=True,
            )
            self.thread.start()

            deadline = time.monotonic() + 5.0
            ready_since: float | None = None
            while time.monotonic() < deadline:
                if self.startup_error is not None:
                    raise RuntimeError(
                        "LOCAL_COMPUTE_LISTENER_THREAD_FAILED"
                    ) from self.startup_error

                if self.thread is None or not self.thread.is_alive():
                    raise RuntimeError(
                        "LOCAL_COMPUTE_LISTENER_THREAD_EXITED"
                    )

                if self.server.started and self._health_is_ready():
                    ready_since = ready_since or time.monotonic()
                    if time.monotonic() - ready_since >= 0.25:
                        return
                else:
                    ready_since = None

                time.sleep(0.02)

            raise RuntimeError("LOCAL_COMPUTE_LISTENER_START_FAILED")
        except Exception:
            self.stop()
            raise

    def _serve(self) -> None:
        assert self.server is not None
        assert self.listener is not None
        try:
            self.server.run(sockets=[self.listener])
        except BaseException as exc:
            self.startup_error = exc
            self._report_failure("server_thread_failed", exc)
        else:
            if not self.server.should_exit:
                error = RuntimeError("LOCAL_COMPUTE_LISTENER_THREAD_EXITED")
                self.startup_error = error
                self._report_failure("server_thread_exited", error)

    def ensure_running(self) -> None:
        if self.startup_error is not None:
            raise RuntimeError("LOCAL_COMPUTE_LISTENER_THREAD_FAILED") from self.startup_error
        if self.thread is None or not self.thread.is_alive() or self.server is None or not self.server.started:
            raise RuntimeError("LOCAL_COMPUTE_LISTENER_THREAD_EXITED")

    def _report_failure(self, stage: str, error: BaseException) -> None:
        if self.failure_reporter is not None:
            self.failure_reporter(stage, error)

    def _health_is_ready(self) -> bool:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{self.port}/health",
                timeout=0.2,
            ) as response:
                if response.status != 200:
                    return False
                payload = response.read().decode("utf-8")
                return (
                    '"status":"ok"' in payload
                    and '"service":"zkd-compute-control"' in payload
                )
        except (OSError, urllib.error.URLError, TimeoutError):
            return False

    def stop(self) -> None:
        server = self.server
        thread = self.thread
        listener = self.listener

        if server is not None:
            server.should_exit = True

        # The listener is supplied by this owner, so close it immediately to
        # guarantee a stop releases the loopback port even if Uvicorn is
        # waiting for a background lifespan task to finish.
        if listener is not None:
            try:
                listener.close()
            except OSError:
                pass

        if thread is not None:
            thread.join(timeout=5)
            if thread.is_alive() and server is not None:
                server.force_exit = True
                thread.join(timeout=2)

        self.listener = None
        self.server = None
        self.thread = None
        self.runtime.bound_port = None
