"""Windows product launcher for the local-first ZKD Compute runtime.

The normal ``--background`` entry point is intentionally quiet. ``--status``
emits metadata only; it never emits keys, grants, MACs, or pairing tokens.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import getpass
import json
import signal
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import os
from pathlib import Path


_NO_CONSOLE_STREAM_HANDLES: list[object] = []


class _DiscardTextStream:
    """Last-resort text sink for a frozen Windows process with no console."""

    closed = False
    encoding = "utf-8"
    errors = "replace"

    def write(self, value: str) -> int:
        return len(value)

    def flush(self) -> None:
        return None

    def isatty(self) -> bool:
        return False

    def writable(self) -> bool:
        return True


def _stream_is_usable(stream: object | None) -> bool:
    """Check the operations used by tqdm/logging without emitting output."""
    if stream is None or bool(getattr(stream, "closed", False)):
        return False
    try:
        stream.write("")
        stream.flush()
        isatty = getattr(stream, "isatty", None)
        if callable(isatty):
            isatty()
        fileno = getattr(stream, "fileno", None)
        if callable(fileno):
            fileno()
    except (AttributeError, OSError, TypeError, ValueError):
        return False
    return True


def _safe_no_console_stream() -> object:
    try:
        handle = open(os.devnull, "w", encoding="utf-8")
    except OSError:
        return _DiscardTextStream()
    _NO_CONSOLE_STREAM_HANDLES.append(handle)
    return handle


def _ensure_standard_streams_for_windowed_runtime() -> None:
    """Supply usable streams only for a frozen Windows no-console process.

    PyInstaller's ``console=False`` mode can expose streams as ``None`` *or*
    as objects backed by invalid Windows handles.  ZKD configures file-backed
    structured logging below; this early guard protects dependencies such as
    tqdm/transformers before they can probe or write an unusable console.
    """

    if not getattr(sys, "frozen", False) or sys.platform != "win32":
        return
    for attribute in ("stdout", "stderr"):
        if not _stream_is_usable(getattr(sys, attribute, None)):
            setattr(sys, attribute, _safe_no_console_stream())


def _disable_frozen_model_progress() -> None:
    """Disable progress rendering before any embedding-model import path."""
    if not getattr(sys, "frozen", False) or sys.platform != "win32":
        return

    # Set before importing model packages: tqdm reads this configuration when
    # it creates a progress bar, and Hugging Face honors its dedicated flag.
    os.environ.setdefault("TQDM_DISABLE", "1")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

    try:
        from huggingface_hub.utils import disable_progress_bars
    except ImportError:
        disable_progress_bars = None
    if disable_progress_bars is not None:
        disable_progress_bars()

    try:
        from transformers.utils import logging as transformers_logging
    except ImportError:
        transformers_logging = None
    if transformers_logging is not None:
        transformers_logging.disable_progress_bar()


def _report_fatal_error(message: str) -> None:
    """Best-effort console diagnostic that can never mask the original error."""
    try:
        sys.stderr.write(message + "\n")
        sys.stderr.flush()
    except (AttributeError, OSError, TypeError, ValueError):
        pass


_ensure_standard_streams_for_windowed_runtime()
_disable_frozen_model_progress()

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.local_compute.catalog import LocalCatalog
from app.local_compute.credentials import WindowsDpapiDeviceCredentialStore, public_key_b64
from app.local_compute.deployment_profile import ComputeDeploymentProfile, DeploymentProfile, get_profile, provision_staging_public_key
from app.local_compute.pairing_uri import PairingUriError, parse_pairing_uri
from app.local_compute.product_paths import local_model_cache_path
from app.local_compute.provisioning import E5ModelProvisioner, GenerationRuntimeManager
from app.local_compute.runtime import LocalComputeRuntime
from app.local_compute.server import LoopbackControlServer
from app.local_compute.settings import LocalComputeSettings
from app.local_compute.single_instance import AlreadyRunningError, WindowsSingleInstance
from app.local_compute.protocol import ProtocolCommand, parse_protocol_uri
from app.local_compute.tray import WindowsTray


USER_AGENT = "ZKD-Compute/0.1.0"
_DIAGNOSTIC_PAYLOAD_ENV = "ZKD_COMPUTE_DIAGNOSTIC_PAYLOAD_B64"
_active_profile = get_profile()


def active_profile() -> DeploymentProfile:
    return _active_profile


def select_profile(value: str) -> None:
    global _active_profile
    _active_profile = get_profile(value)


def platform_api() -> str:
    return active_profile().platform_origin


def bootstrap_log(
    stage: str,
    error: BaseException | None = None,
    *,
    port: int | None = None,
) -> None:
    """Write safe startup diagnostics before normal application logging exists."""
    try:
        path = data_root() / "logs" / "bootstrap.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": int(time.time()),
            "stage": stage,
        }
        if port is not None:
            record["port"] = port
        if error is not None:
            record["exception_class"] = type(error).__name__
            # Do not persist arbitrary exception text: it may include remote
            # credentials, grants, headers, or untrusted document data.
            record["message"] = "startup operation failed"
            frames = traceback.extract_tb(error.__traceback__)
            if frames:
                frame = frames[-1]
                # File/function/line is enough to diagnose bootstrap code
                # without persisting an arbitrary exception payload.
                record["failure_location"] = (
                    f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}"
                )
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")
    except Exception:
        # Bootstrap diagnostics must never block the local runtime.
        pass


def data_root() -> Path:
    return active_profile().data_root()


def credential_path() -> Path:
    return data_root() / "state" / "device-key.dpapi"


def platform_public_key_path() -> Path:
    return active_profile().public_key_path


def read_platform_public_key() -> str:
    path = platform_public_key_path()
    if not path.is_file():
        raise RuntimeError("PLATFORM_PUBLIC_KEY_NOT_FOUND")
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise RuntimeError("PLATFORM_PUBLIC_KEY_EMPTY")
    return value


def credential_store() -> WindowsDpapiDeviceCredentialStore:
    return WindowsDpapiDeviceCredentialStore(credential_path())


def ensure_device_key() -> Ed25519PrivateKey:
    store = credential_store()
    key = store.load_private_key()
    if key is None:
        key = Ed25519PrivateKey.generate()
        store.save_private_key(key)
    return key


def build_settings() -> LocalComputeSettings:
    root = data_root()
    return LocalComputeSettings(
        data_root=root,
        bind_port=0,
        embedding_model_cache_dir=local_model_cache_path(),
        production_origin=platform_api(),
        platform_base_url=platform_api(),
        control_auto_start=False,
        platform_grant_verification_public_key=read_platform_public_key(),
    )


def post_json(path: str, payload: dict) -> dict:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(platform_api() + path, data=body, headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": USER_AGENT}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"PLATFORM_HTTP_{exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("PLATFORM_UNREACHABLE") from exc


def catalog() -> LocalCatalog:
    instance = LocalCatalog(data_root() / "state" / "catalog.sqlite3")
    instance.initialize()
    return instance


def paired_state() -> dict | None:
    return catalog().get_paired_device_state()


def show_status() -> int:
    paired = paired_state()
    status = {"profile": active_profile().name.value, "platform_base_url": platform_api(), "data_root": str(data_root()), "pairing_state": "PAIRED" if paired else "NOT_PAIRED", "embedding_model_ready": E5ModelProvisioner(local_model_cache_path()).is_ready()}
    if paired:
        status.update({"device_id": paired["device_id"], "credential_epoch": paired["credential_epoch"]})
    print(json.dumps(status, separators=(",", ":")))
    return 0 if paired else 2


def run_developer_answer_pipeline() -> int:
    """Run one all-document answer request from stdin without opening HTTP.

    This is a developer-only packaged-image diagnostic. It deliberately has
    no listener, grant bypass, persisted request body, or answer-text output.
    Restricting the payload to the all-document shape keeps it useful for
    release verification without turning the launcher into a general command
    execution surface.
    """

    raw_payload = _read_developer_diagnostic_payload()
    if not raw_payload or len(raw_payload) > 8 * 1024:
        raise RuntimeError("DIAGNOSTIC_PAYLOAD_REQUIRED")
    try:
        payload = json.loads(raw_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("DIAGNOSTIC_PAYLOAD_INVALID") from exc

    if (
        not isinstance(payload, dict)
        or set(payload) != {"query_text", "document_ids", "answer_mode"}
        or not isinstance(payload["query_text"], str)
        or payload["document_ids"] is not None
        or not isinstance(payload["answer_mode"], str)
    ):
        raise RuntimeError("DIAGNOSTIC_PAYLOAD_INVALID")

    from app.local_compute.generation import GenerationRoutingRequest, LocalAnswerService
    from app.local_compute.runtime_logging import configure_local_compute_logging

    settings = build_settings()
    configure_local_compute_logging(settings.logs_path)
    runtime = LocalComputeRuntime(settings)
    router = runtime.generation_router()
    service = LocalAnswerService(
        settings,
        LocalCatalog(settings.catalog_path),
        router,
        profile=router.local_provider.profile,
    )
    stages: list[str] = []

    async def run() -> object:
        return await service.answer(
            request_id="developer-answer-pipeline",
            query_text=payload["query_text"],
            document_ids=None,
            answer_mode=payload["answer_mode"],
            routing=GenerationRoutingRequest(),
            stage_reporter=lambda stage, _boundary: stages.append(stage),
        )

    response = asyncio.run(run())
    stages.append("answers_serialization_begin")
    from fastapi.responses import JSONResponse

    serialized = JSONResponse(
        content={"request_id": "developer-answer-pipeline", **response.as_dict()}
    ).body
    stages.append("answers_serialization_done")
    stages.append("answers_response_ready")
    print(
        json.dumps(
            {
                "diagnostic": "developer_answer_pipeline",
                "status": "PASS",
                "answer_mode": response.answer_mode,
                "stages": stages,
                "response_serializable": isinstance(response.as_dict(), dict)
                and bool(serialized),
                "generation_status": response.result.status.value,
            },
            separators=(",", ":"),
        )
    )
    return 0


def _read_developer_diagnostic_payload() -> bytes:
    """Read the hidden diagnostic payload without requiring a visible console."""
    raw_payload = b""
    stdin_buffer = getattr(getattr(sys, "stdin", None), "buffer", None)
    if stdin_buffer is not None:
        raw_payload = stdin_buffer.read(8 * 1024 + 1)
    if not raw_payload:
        # A PyInstaller windowed executable has no usable stdin.  This is a
        # hidden developer-only acceptance path, so a bounded, process-local
        # payload may be supplied by the release harness instead.  Consume it
        # immediately so it cannot propagate to child processes or logs.
        encoded_payload = os.environ.pop(_DIAGNOSTIC_PAYLOAD_ENV, "")
        if encoded_payload:
            try:
                raw_payload = base64.b64decode(
                    encoded_payload,
                    validate=True,
                )
            except (ValueError, UnicodeError):
                raise RuntimeError("DIAGNOSTIC_PAYLOAD_INVALID") from None
    return raw_payload


def pair(pairing_request_id: str, pairing_token: str) -> int:
    """Complete a short-lived pairing request without persisting its token."""
    existing = paired_state()
    if existing is not None:
        return 0
    key, settings = ensure_device_key(), build_settings()
    runtime = LocalComputeRuntime(settings, credential_store=credential_store())
    server = LoopbackControlServer(runtime, failure_reporter=bootstrap_log)
    runtime.start()
    try:
        server.start()
        signature = base64.b64encode(key.sign(f"pairing|{pairing_request_id}|{pairing_token}".encode("utf-8"))).decode("ascii")
        completed = post_json(f"/api/v1/compute/control/pairing-challenges/{pairing_request_id}/complete", {"pairing_token": pairing_token, "public_key": public_key_b64(key), "signature": signature, "protocol_version": settings.protocol_version, "runtime_version": settings.runtime_version, "friendly_label": "ZKD Compute Windows"})
        runtime.control_channel.complete_pairing_state(completed["device_id"], None, int(completed.get("credential_epoch", 1)))
        runtime.control_channel.tick()  # metadata-only presence; browser confirmation remains authoritative.
        return 0
    finally:
        server.stop()
        runtime.shutdown()


def interactive_pair() -> int:
    request_id = input("Pairing request ID: ").strip()
    token = getpass.getpass("Pairing token: ").strip()
    if not request_id or not token:
        raise RuntimeError("PAIRING_REQUEST_REQUIRED")
    return pair(request_id, token)


def run_background() -> int:
    paired = paired_state()
    bootstrap_log("local_state_loaded")
    if paired is None:
        bootstrap_log("pairing_required")
        return 2
    settings = build_settings()
    model_ready = E5ModelProvisioner(settings.embedding_model_cache_dir).is_ready()
    runtime = LocalComputeRuntime(settings, credential_store=credential_store())
    server = LoopbackControlServer(runtime, failure_reporter=bootstrap_log)
    stopping = threading.Event()
    restarting = threading.Event()
    generation = GenerationRuntimeManager(settings.models_path / "generation-runtime")
    tray = WindowsTray(runtime, logs_path=settings.logs_path, open_url=platform_api(), quit_requested=stopping, restart_requested=restarting, profile_label=active_profile().tray_prefix)

    def request_stop(_signal=None, _frame=None) -> None:
        stopping.set()

    for signal_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        signal_value = getattr(signal, signal_name, None)
        if signal_value is not None:
            signal.signal(signal_value, request_stop)
    bootstrap_log("runtime_start_begin")
    runtime.start()
    bootstrap_log("runtime_start_complete")
    try:
        bootstrap_log("server_start_begin")
        server.start()
        bootstrap_log("server_bound", port=server.port)
        bootstrap_log("server_ready")
        server.ensure_running()
        bootstrap_log("control_tick_begin")
        runtime.control_channel.tick()
        bootstrap_log("control_tick_result")
        server.ensure_running()
        runtime.control_channel.start()
        tray.start()
        bootstrap_log("control_thread_started")
        # A release-bundled, checksum-pinned sidecar may be supplied later.
        # Never launch/download an unverified binary merely because it exists.
        if model_ready:
            runtime.update_generation_capability("MODEL_UNAVAILABLE")
        bootstrap_log("runtime_ready")
        while not stopping.wait(0.5):
            tray.refresh()
            if (
                runtime.control_channel.should_run()
                and not runtime.control_channel.is_running()
            ):
                # The channel contains its own retry policy. This is only a
                # final liveness guard for an unexpectedly exited daemon.
                bootstrap_log("control_thread_restart")
                runtime.control_channel.start()
            if restarting.is_set():
                restarting.clear()
                runtime.control_channel.stop()
                server.stop()
                runtime.recreate_endpoint_generation()
                server.start()
                runtime.control_channel.start()
                tray.refresh()
        return 0
    finally:
        tray.stop()
        generation.stop()
        server.stop()
        runtime.shutdown()


def run_protocol(command: ProtocolCommand) -> int:
    """Protocol invocation intentionally has no arguments, files, or secrets."""
    if command is ProtocolCommand.OPEN:
        try:
            os.startfile(platform_api())  # noqa: S606 - profile-owned fixed URL only
        except OSError as exc:
            bootstrap_log("protocol_open_failed", exc)
        return 0
    # A second start invocation meets the mutex and exits without changing the
    # endpoint generation or binding a second loopback port.
    with WindowsSingleInstance(active_profile().mutex_name):
        return run_background()


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if len(raw_argv) == 1 and raw_argv[0].lower().startswith("zkd:"):
        command = parse_protocol_uri(raw_argv[0])
        if command is None:
            bootstrap_log("protocol_uri_rejected")
            return 0
        try:
            bootstrap_log("protocol_invoked")
            return run_protocol(command)
        except AlreadyRunningError:
            bootstrap_log("already_running")
            return 0
    parser = argparse.ArgumentParser(prog="zkd-compute", description="ZKD Compute Windows companion")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--pair", action="store_true")
    parser.add_argument("--pair-uri")
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--profile", choices=[item.value for item in ComputeDeploymentProfile], default=ComputeDeploymentProfile.PRODUCTION.value)
    parser.add_argument("--provision-staging-key", action="store_true")
    parser.add_argument("--diagnostic-answer-pipeline", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--data-root", help=argparse.SUPPRESS)
    arguments = parser.parse_args(raw_argv)
    select_profile(arguments.profile)
    if arguments.data_root:
        import os
        os.environ["ZKD_COMPUTE_DATA_ROOT"] = str(Path(arguments.data_root).resolve())
    if sum(bool(value) for value in (arguments.status, arguments.pair, arguments.pair_uri, arguments.background, arguments.provision_staging_key, arguments.diagnostic_answer_pipeline)) > 1:
        parser.error("Choose one launcher mode.")
    try:
        bootstrap_log("launcher_enter")
        if arguments.status:
            return show_status()
        if arguments.provision_staging_key:
            provision_staging_public_key(active_profile())
            return 0
        if arguments.diagnostic_answer_pipeline:
            return run_developer_answer_pipeline()
        if arguments.pair_uri:
            request = parse_pairing_uri(arguments.pair_uri)
            return pair(request.request_id, request.token)
        if arguments.pair:
            return interactive_pair()
        with WindowsSingleInstance(active_profile().mutex_name):
            return run_background()
    except AlreadyRunningError:
        bootstrap_log("already_running")
        return 0
    except PairingUriError as exc:
        bootstrap_log("pairing_uri_error", exc)
        _report_fatal_error(f"ZKD_COMPUTE_ERROR:{exc}")
        return 2
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        bootstrap_log("launcher_failed", exc)
        # Never include URI, request body, grant, pairing token, or key data.
        _report_fatal_error(f"ZKD_COMPUTE_ERROR:{type(exc).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
