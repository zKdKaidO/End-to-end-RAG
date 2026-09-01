from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

import pytest
import httpx
from fastapi.testclient import TestClient

from app.local_compute.api import create_local_compute_app
from app.local_compute.errors import LocalComputeErrorCode
from app.local_compute.jobs import LocalJobStore
from app.local_compute.runtime import LocalComputeRuntime, RuntimeState
from app.local_compute.server import LoopbackControlServer
from app.local_compute.settings import PRODUCT_ORIGIN, LocalComputeSettings


@pytest.fixture
def runtime(tmp_path):
    instance = LocalComputeRuntime(
        LocalComputeSettings(
            data_root=tmp_path / "ZKD" / "Compute",
            development_mode=True,
            development_origins=("http://localhost:5173",),
            session_lifetime_seconds=120,
        )
    )
    instance.start()
    yield instance
    instance.shutdown()


@pytest.fixture
def client(runtime):
    return TestClient(create_local_compute_app(runtime))


def _session(client, origin=PRODUCT_ORIGIN):
    response = client.post("/v1/sessions", headers={"Origin": origin, "X-ZKD-Local-Grant": "development-test-grant"})
    assert response.status_code == 200, response.text
    return response.json()


def _signed_headers(session, method, path, body=b"", origin=PRODUCT_ORIGIN, timestamp=None, nonce=None, protocol="zkd-compute-v1"):
    timestamp = str(int(time.time()) if timestamp is None else timestamp)
    nonce = nonce or str(uuid.uuid4())
    body_hash = hashlib.sha256(body).hexdigest()
    payload = "|".join((method, path, timestamp, nonce, body_hash)).encode()
    mac = hmac.new(session["session_key"].encode(), payload, hashlib.sha256).hexdigest()
    return {
        "Origin": origin,
        "X-ZKD-Local-Session": session["local_session_id"],
        "X-ZKD-Timestamp": timestamp,
        "X-ZKD-Nonce": nonce,
        "X-ZKD-MAC": mac,
        "X-ZKD-Protocol-Version": protocol,
    }


def test_loopback_only_and_data_root(runtime):
    assert runtime.settings.bind_host == "127.0.0.1"
    assert runtime.settings.catalog_path.exists()
    assert runtime.settings.logs_path.exists()
    assert runtime.settings.tmp_path.exists()
    with pytest.raises(ValueError, match="LOOPBACK_ONLY"):
        LocalComputeSettings(bind_host="0.0.0.0")


def test_audit_log_is_redirected_and_does_not_store_authentication_material(client, runtime):
    session = _session(client)
    client.get("/v1/runtime", headers=_signed_headers(session, "GET", "/v1/runtime"))
    events = [json.loads(line) for line in (runtime.settings.logs_path / "runtime.jsonl").read_text().splitlines()]
    assert events[-1]["operation"] == "GET /v1/runtime"
    assert "session_key" not in (runtime.settings.logs_path / "runtime.jsonl").read_text()


def test_production_mode_fails_closed_without_real_grant_verifier(tmp_path):
    runtime = LocalComputeRuntime(LocalComputeSettings(data_root=tmp_path))
    runtime.start()
    client = TestClient(create_local_compute_app(runtime))
    response = client.post("/v1/sessions", headers={"Origin": PRODUCT_ORIGIN, "X-ZKD-Local-Grant": "anything"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == LocalComputeErrorCode.NOT_PAIRED.value


def test_allowed_origin_preflight_includes_pna_and_never_wildcard(client):
    response = client.options(
        "/v1/probe/binary",
        headers={
            "Origin": PRODUCT_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Private-Network": "true",
        },
    )
    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == PRODUCT_ORIGIN
    assert response.headers["access-control-allow-private-network"] == "true"
    assert response.headers["access-control-allow-origin"] != "*"


def test_foreign_origin_is_denied_without_runtime_metadata(client):
    response = client.get("/v1/runtime", headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == LocalComputeErrorCode.ORIGIN_NOT_ALLOWED.value
    assert "protocol_version" not in response.text


def test_authenticated_runtime_and_capabilities(client):
    session = _session(client)
    response = client.get("/v1/runtime", headers=_signed_headers(session, "GET", "/v1/runtime"))
    assert response.status_code == 200
    assert response.json()["state"] == RuntimeState.READY.value
    assert response.json()["protocol_version"] == "zkd-compute-v1"
    capabilities = client.get("/v1/capabilities", headers=_signed_headers(session, "GET", "/v1/capabilities"))
    assert capabilities.status_code == 200
    assert set(capabilities.json()["capabilities"]) == {"pdf_processing", "chunking", "embedding", "indexing", "retrieval", "generation"}
    assert {key: value for key, value in capabilities.json()["capabilities"].items() if key != "generation"} == {
        "pdf_processing": "READY", "chunking": "READY", "embedding": "READY", "indexing": "READY", "retrieval": "READY",
    }
    assert capabilities.json()["capabilities"]["generation"] in {"READY", "MODEL_UNAVAILABLE", "DEGRADED"}


def test_authentication_rejects_missing_invalid_replayed_and_body_hash_mismatch(client):
    assert client.get("/v1/runtime", headers={"Origin": PRODUCT_ORIGIN}).json()["error"]["code"] == "AUTH_REQUIRED"
    session = _session(client)
    headers = _signed_headers(session, "GET", "/v1/runtime")
    assert client.get("/v1/runtime", headers=headers).status_code == 200
    replay = client.get("/v1/runtime", headers=headers)
    assert replay.status_code == 409
    assert replay.json()["error"]["code"] == "REPLAY_DETECTED"
    body = b"synthetic-bytes"
    wrong = _signed_headers(session, "POST", "/v1/probe/binary", b"other")
    response = client.post("/v1/probe/binary", content=body, headers=wrong)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_INVALID"


def test_protocol_mismatch_and_session_expiry(client, runtime, monkeypatch):
    session = _session(client)
    mismatch = client.get("/v1/runtime", headers=_signed_headers(session, "GET", "/v1/runtime", protocol="unknown-v99"))
    assert mismatch.status_code == 426
    assert mismatch.json()["error"]["code"] == "UPDATE_REQUIRED"
    assert runtime.state == RuntimeState.UPDATE_REQUIRED
    expired = _signed_headers(session, "GET", "/v1/runtime", timestamp=int(time.time()) - 1000)
    result = client.get("/v1/runtime", headers=expired)
    assert result.status_code == 401
    assert result.json()["error"]["code"] == "SESSION_EXPIRED"


def test_binary_transport_payload_limit_and_direct_body_delivery(client, runtime):
    session = _session(client)
    body = b"synthetic-pdf-like-payload"
    response = client.post("/v1/probe/binary", content=body, headers=_signed_headers(session, "POST", "/v1/probe/binary", body))
    assert response.status_code == 200
    assert response.json()["received_bytes"] == len(body)
    too_large = b"x" * (runtime.settings.request_body_max_bytes + 1)
    response = client.post("/v1/probe/binary", content=too_large, headers=_signed_headers(session, "POST", "/v1/probe/binary", too_large))
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_ephemeral_listener_and_catalog_job_persistence(runtime):
    listener = runtime.bind_ephemeral_socket()
    try:
        assert listener.getsockname()[0] == "127.0.0.1"
        assert runtime.bound_port and runtime.bound_port > 0
    finally:
        listener.close()
    jobs = LocalJobStore(runtime.catalog)
    job_id = jobs.enqueue_skeleton("PREPARE_DOCUMENT")
    assert jobs.get(job_id)["state"] == "QUEUED"
    restarted = LocalComputeRuntime(runtime.settings)
    restarted.start()
    assert LocalJobStore(restarted.catalog).get(job_id)["operation"] == "PREPARE_DOCUMENT"


def test_real_loopback_http_transport_with_synthetic_binary(runtime):
    server = LoopbackControlServer(runtime)
    server.start()
    try:
        base_url = f"http://127.0.0.1:{server.port}"
        with httpx.Client(base_url=base_url, timeout=3) as remote:
            preflight = remote.options(
                "/v1/probe/binary",
                headers={
                    "Origin": PRODUCT_ORIGIN,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Private-Network": "true",
                },
            )
            assert preflight.status_code == 204
            assert preflight.headers["access-control-allow-private-network"] == "true"
            created = remote.post("/v1/sessions", headers={"Origin": PRODUCT_ORIGIN, "X-ZKD-Local-Grant": "development-test-grant"})
            session = created.json()
            body = b"isolated-synthetic-binary-body"
            uploaded = remote.post("/v1/probe/binary", content=body, headers=_signed_headers(session, "POST", "/v1/probe/binary", body))
            assert uploaded.status_code == 200
            assert uploaded.json()["received_bytes"] == len(body)
            denied = remote.options("/v1/probe/binary", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
            assert denied.status_code == 403
    finally:
        server.stop()
