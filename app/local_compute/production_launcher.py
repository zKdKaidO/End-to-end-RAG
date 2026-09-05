"""Windows product launcher for the local-first ZKD Compute runtime.

The normal ``--background`` entry point is intentionally quiet. ``--status``
emits metadata only; it never emits keys, grants, MACs, or pairing tokens.
"""

from __future__ import annotations

import argparse
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
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.local_compute.catalog import LocalCatalog
from app.local_compute.credentials import WindowsDpapiDeviceCredentialStore, public_key_b64
from app.local_compute.pairing_uri import PairingUriError, parse_pairing_uri
from app.local_compute.product_paths import local_model_cache_path, product_data_root
from app.local_compute.provisioning import E5ModelProvisioner, GenerationRuntimeManager
from app.local_compute.runtime import LocalComputeRuntime
from app.local_compute.server import LoopbackControlServer
from app.local_compute.settings import LocalComputeSettings
from app.local_compute.single_instance import AlreadyRunningError, WindowsSingleInstance


PLATFORM_API = "https://rag.zkd.id.vn"
USER_AGENT = "ZKD-Compute/0.1.0"


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
    return product_data_root()


def credential_path() -> Path:
    return data_root() / "state" / "device-key.dpapi"


def platform_public_key_path() -> Path:
    return data_root() / "config" / "platform-grant-public.b64"


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
        platform_base_url=PLATFORM_API,
        control_auto_start=False,
        platform_grant_verification_public_key=read_platform_public_key(),
    )


def post_json(path: str, payload: dict) -> dict:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(PLATFORM_API + path, data=body, headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": USER_AGENT}, method="POST")
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
    status = {"data_root": str(data_root()), "pairing_state": "PAIRED" if paired else "NOT_PAIRED", "embedding_model_ready": E5ModelProvisioner(local_model_cache_path()).is_ready()}
    if paired:
        status.update({"device_id": paired["device_id"], "credential_epoch": paired["credential_epoch"]})
    print(json.dumps(status, separators=(",", ":")))
    return 0 if paired else 2


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
    generation = GenerationRuntimeManager(settings.models_path / "generation-runtime")

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
        bootstrap_log("control_thread_started")
        # A release-bundled, checksum-pinned sidecar may be supplied later.
        # Never launch/download an unverified binary merely because it exists.
        if model_ready:
            runtime.update_generation_capability("MODEL_UNAVAILABLE")
        bootstrap_log("runtime_ready")
        while not stopping.wait(0.5):
            pass
        return 0
    finally:
        generation.stop()
        server.stop()
        runtime.shutdown()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="zkd-compute", description="ZKD Compute Windows companion")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--pair", action="store_true")
    parser.add_argument("--pair-uri")
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--data-root", help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    if arguments.data_root:
        import os
        os.environ["ZKD_COMPUTE_DATA_ROOT"] = str(Path(arguments.data_root).resolve())
    if sum(bool(value) for value in (arguments.status, arguments.pair, arguments.pair_uri, arguments.background)) > 1:
        parser.error("Choose one launcher mode.")
    try:
        bootstrap_log("launcher_enter")
        if arguments.status:
            return show_status()
        if arguments.pair_uri:
            request = parse_pairing_uri(arguments.pair_uri)
            return pair(request.request_id, request.token)
        if arguments.pair:
            return interactive_pair()
        with WindowsSingleInstance():
            return run_background()
    except AlreadyRunningError:
        bootstrap_log("already_running")
        return 0
    except PairingUriError as exc:
        bootstrap_log("pairing_uri_error", exc)
        print(f"ZKD_COMPUTE_ERROR:{exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        bootstrap_log("launcher_failed", exc)
        # Never include URI, request body, grant, pairing token, or key data.
        print(f"ZKD_COMPUTE_ERROR:{type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
