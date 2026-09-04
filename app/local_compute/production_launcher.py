"""Persistent Windows launcher for ZKD Compute."""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.local_compute.catalog import LocalCatalog
from app.local_compute.credentials import WindowsDpapiDeviceCredentialStore, public_key_b64
from app.local_compute.runtime import LocalComputeRuntime
from app.local_compute.server import LoopbackControlServer
from app.local_compute.settings import LocalComputeSettings, default_data_root


PLATFORM_API = "https://rag.zkd.id.vn"
USER_AGENT = "ZKD-Compute/0.1.0"


def data_root() -> Path:
    return default_data_root()


def credential_path() -> Path:
    return data_root() / "state" / "device-key.dpapi"


def platform_public_key_path() -> Path:
    return data_root() / "config" / "platform-grant-public.b64"


def read_platform_public_key() -> str:
    path = platform_public_key_path()

    if not path.is_file():
        raise RuntimeError(
            f"PLATFORM_PUBLIC_KEY_NOT_FOUND: {path}"
        )

    value = path.read_text(
        encoding="utf-8"
    ).strip()

    if not value:
        raise RuntimeError(
            "PLATFORM_PUBLIC_KEY_EMPTY"
        )

    return value


def credential_store() -> WindowsDpapiDeviceCredentialStore:
    return WindowsDpapiDeviceCredentialStore(
        credential_path()
    )


def ensure_device_key() -> Ed25519PrivateKey:
    store = credential_store()
    key = store.load_private_key()

    if key is not None:
        return key

    key = Ed25519PrivateKey.generate()
    store.save_private_key(key)

    return key


def build_settings() -> LocalComputeSettings:
    return LocalComputeSettings(
        data_root=data_root(),
        bind_port=0,
        platform_base_url=PLATFORM_API,
        control_auto_start=False,
        platform_grant_verification_public_key=read_platform_public_key(),
    )


def post_json(path: str, payload: dict) -> dict:
    body = json.dumps(
        payload,
        separators=(",", ":"),
    ).encode("utf-8")

    request = urllib.request.Request(
        PLATFORM_API + path,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=15,
        ) as response:
            raw = response.read()

            if not raw:
                return {}

            return json.loads(raw)

    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"PLATFORM_HTTP_{exc.code}: {response_body}"
        ) from exc

    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"PLATFORM_UNREACHABLE: {exc}"
        ) from exc


def catalog() -> LocalCatalog:
    root = data_root()

    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    local_catalog = LocalCatalog(
        root / "state" / "catalog.sqlite3"
    )

    local_catalog.initialize()

    return local_catalog


def paired_state() -> dict | None:
    return catalog().get_paired_device_state()


def show_status() -> int:
    key = ensure_device_key()
    paired = paired_state()

    print(
        "DATA_ROOT =",
        data_root(),
    )

    print(
        "DEVICE_KEY =",
        credential_path(),
    )

    print(
        "PUBLIC_KEY =",
        public_key_b64(key),
    )

    if paired is None:
        print(
            "PAIRING_STATE = NOT_PAIRED"
        )

        return 2

    print(
        "PAIRING_STATE = PAIRED"
    )

    print(
        "DEVICE_ID =",
        paired["device_id"],
    )

    print(
        "CREDENTIAL_EPOCH =",
        paired["credential_epoch"],
    )

    return 0


def pair(
    pairing_request_id: str,
    pairing_token: str,
) -> int:
    existing = paired_state()

    if existing is not None:
        print(
            "PAIRING_STATE = ALREADY_PAIRED"
        )

        print(
            "DEVICE_ID =",
            existing["device_id"],
        )

        return 0

    key = ensure_device_key()
    runtime_settings = build_settings()

    runtime = LocalComputeRuntime(
        runtime_settings,
        credential_store=credential_store(),
    )

    server = LoopbackControlServer(runtime)

    runtime.start()

    try:
        server.start()

        message = (
            f"pairing|{pairing_request_id}|"
            f"{pairing_token}"
        ).encode("utf-8")

        signature = base64.b64encode(
            key.sign(message)
        ).decode("ascii")

        completed = post_json(
            (
                "/api/v1/compute/control/"
                "pairing-challenges/"
                f"{pairing_request_id}/complete"
            ),
            {
                "pairing_token": pairing_token,
                "public_key": public_key_b64(
                    key
                ),
                "signature": signature,
                "protocol_version": runtime_settings.protocol_version,
                "runtime_version": runtime_settings.runtime_version,
                "friendly_label": "ZKD Compute Windows",
            },
        )

        device_id = completed[
            "device_id"
        ]

        credential_epoch = int(
            completed.get(
                "credential_epoch",
                1,
            )
        )

        runtime.control_channel.complete_pairing_state(
            device_id,
            None,
            credential_epoch,
        )

        print()
        print(
            "SERVER_SIDE_PAIRING_COMPLETE"
        )

        print(
            "DEVICE_ID =",
            device_id,
        )

        print(
            "CREDENTIAL_EPOCH =",
            credential_epoch,
        )

        print(
            "ENDPOINT_PORT =",
            runtime.bound_port,
        )

        print()
        print(
            "Confirm the pairing code in rag.zkd.id.vn."
        )

        input(
            "After the browser says CONFIRMED, press ENTER here... "
        )

        runtime.control_channel.tick()
        runtime.control_channel.start()

        print()
        print(
            "CONTROL_CHANNEL_STATE =",
            runtime.control_channel.state.value,
        )

        print(
            "RUNTIME_STATE =",
            runtime.state.value,
        )

        print(
            "ENDPOINT_PORT =",
            runtime.bound_port,
        )

        return 0

    finally:
        server.stop()
        runtime.shutdown()


def interactive_pair() -> int:
    print(
        "=== ZKD COMPUTE PAIRING ==="
    )

    print()

    pairing_request_id = input(
        "Pairing request ID: "
    ).strip()

    pairing_token = getpass.getpass(
        "Pairing token: "
    ).strip()

    if not pairing_request_id:
        raise RuntimeError(
            "PAIRING_REQUEST_ID_REQUIRED"
        )

    if not pairing_token:
        raise RuntimeError(
            "PAIRING_TOKEN_REQUIRED"
        )

    return pair(
        pairing_request_id,
        pairing_token,
    )


def run() -> int:
    paired = paired_state()

    if paired is None:
        print(
            "ZKD_COMPUTE_NEEDS_PAIRING"
        )

        print(
            "Run: python -m app.local_compute.production_launcher --pair"
        )

        return 2

    ensure_device_key()

    runtime = LocalComputeRuntime(
        build_settings(),
        credential_store=credential_store(),
    )

    server = LoopbackControlServer(runtime)

    runtime.start()

    try:
        server.start()

        runtime.control_channel.tick()
        runtime.control_channel.start()

        paired = paired_state()

        print(
            "ZKD_COMPUTE_READY"
        )

        print(
            "DEVICE_ID =",
            paired["device_id"],
        )

        print(
            "CREDENTIAL_EPOCH =",
            paired["credential_epoch"],
        )

        print(
            "ENDPOINT_PORT =",
            runtime.bound_port,
        )

        print(
            "CONTROL_CHANNEL_STATE =",
            runtime.control_channel.state.value,
        )

        print(
            "RUNTIME_STATE =",
            runtime.state.value,
        )

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print()
        print(
            "Stopping ZKD Compute..."
        )

        return 0

    finally:
        server.stop()
        runtime.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="zkd-compute",
        description="ZKD Compute persistent Windows runtime.",
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Show persistent device/pairing status.",
    )

    parser.add_argument(
        "--pair",
        action="store_true",
        help="Pair this Windows device with the platform.",
    )

    args = parser.parse_args()

    if args.status and args.pair:
        parser.error(
            "--status and --pair cannot be used together."
        )

    try:
        if args.status:
            return show_status()

        if args.pair:
            return interactive_pair()

        return run()

    except KeyboardInterrupt:
        return 0

    except Exception as exc:
        print(
            f"ZKD_COMPUTE_ERROR: {exc}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    sys.exit(main())