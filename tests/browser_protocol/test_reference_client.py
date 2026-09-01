from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from app.local_compute.sessions import LocalSessionManager, request_mac as server_request_mac
from tools.browser_protocol.reference_client import (
    BrowserComputeProtocolError,
    BrowserComputeReferenceClient,
    BrowserComputeRequestSigner,
    BrowserLocalSession,
    DeviceDiscovery,
    canonical_transcript,
    request_mac,
    serialize_json_once,
)


FIXTURE = Path(__file__).parents[1] / "fixtures" / "browser_compute_hmac_v1.json"


def _ready_device(**overrides):
    payload = {
        "device_id": "device-1",
        "state": "READY",
        "protocol_version": "zkd-compute-v1",
        "runtime_version": "0.1.0",
        "endpoint_generation": "generation-1",
        "endpoint_port": 43123,
        "capabilities": {"documents": "READY", "retrieval": "READY", "answer": "READY"},
    }
    payload.update(overrides)
    return payload


def test_fixture_vectors_match_browser_reference_and_compute_verifier(monkeypatch):
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for vector in fixture["vectors"]:
        body = base64.b64decode(vector["raw_body_base64"])
        assert canonical_transcript(
            vector["method"], vector["path"], vector["timestamp"], vector["nonce"], body
        ) == vector["canonical_transcript"]
        assert request_mac(
            vector["session_secret"], vector["method"], vector["path"], vector["timestamp"], vector["nonce"], body
        ) == vector["expected_hmac_sha256"]
        assert server_request_mac(
            vector["session_secret"], vector["method"], vector["path"], vector["timestamp"], vector["nonce"], body
        ) == vector["expected_hmac_sha256"]

    vector = fixture["vectors"][1]
    body = base64.b64decode(vector["raw_body_base64"])
    manager = LocalSessionManager(session_lifetime_seconds=60, nonce_lifetime_seconds=60)
    monkeypatch.setattr("app.local_compute.sessions.time.time", lambda: int(vector["timestamp"]))
    session = manager.create_session("https://rag.zkd.id.vn")
    session.session_key = vector["session_secret"]
    headers = {
        "X-ZKD-Local-Session": session.session_id,
        "X-ZKD-Timestamp": vector["timestamp"],
        "X-ZKD-Nonce": vector["nonce"],
        "X-ZKD-MAC": vector["expected_hmac_sha256"],
    }
    assert manager.validate(vector["method"], vector["path"], body, "https://rag.zkd.id.vn", headers, "retrieval") is session


def test_json_is_serialized_once_and_signed_as_exact_utf8_bytes():
    session = BrowserLocalSession("device-1", "generation-1", "http://127.0.0.1:43123", "session-1", "secret-1", 1_800_000_000, frozenset({"retrieval"}), "zkd-compute-v1")
    body = serialize_json_once({"query_text": "doanh nghiệp", "document_ids": ["doc-1"]})
    signer = BrowserComputeRequestSigner(session, clock=lambda: 1_735_689_600, nonce_factory=lambda: "fresh-request-nonce")
    headers = signer.sign("POST", "/v1/queries", body)
    assert headers["X-ZKD-MAC"] == server_request_mac("secret-1", "POST", "/v1/queries", headers["X-ZKD-Timestamp"], headers["X-ZKD-Nonce"], body)
    assert body == b'{"query_text":"doanh nghi\xe1\xbb\x87p","document_ids":["doc-1"]}'


def test_binary_bytes_and_exact_path_are_not_rebuilt_or_relaxed():
    session = BrowserLocalSession("device-1", "generation-1", "http://127.0.0.1:43123", "session-1", "secret-1", 1_800_000_000, frozenset({"documents"}), "zkd-compute-v1")
    body = b"%PDF-1.7\n%\x80\x81\n"
    signer = BrowserComputeRequestSigner(session, clock=lambda: 1_735_689_600, nonce_factory=lambda: "binary-request-nonce")
    headers = signer.sign("PUT", "/v1/documents/doc-1/source", body)
    assert headers["X-ZKD-MAC"] == server_request_mac("secret-1", "PUT", "/v1/documents/doc-1/source", headers["X-ZKD-Timestamp"], headers["X-ZKD-Nonce"], body)
    with pytest.raises(BrowserComputeProtocolError, match="EXACT_PATH"):
        signer.sign("PUT", "/v1/documents/doc-1/source?retry=1", body)


def test_discovery_selection_and_generation_change_discards_memory_only_session():
    client = BrowserComputeReferenceClient()
    client.accept_discovery(_ready_device(), required_capability="retrieval")
    session = client.bootstrap_session({
        "local_session_id": "session-1", "session_key": "secret-1", "expires_at": 1_800_000_000,
        "allowed_operations": ["retrieval"], "protocol_version": "zkd-compute-v1", "endpoint_generation": "generation-1",
    }, required_capability="retrieval")
    assert session.base_url == "http://127.0.0.1:43123"
    client.accept_discovery(_ready_device(endpoint_generation="generation-2"), required_capability="retrieval")
    assert client.session is None
    with pytest.raises(BrowserComputeProtocolError, match="SESSION_REQUIRED"):
        client.signer()


@pytest.mark.parametrize(
    ("state", "expected"),
    [("OFFLINE", "DEVICE_OFFLINE"), ("REVOKED", "DEVICE_REVOKED")],
)
def test_discovery_refuses_offline_or_revoked_devices(state, expected):
    client = BrowserComputeReferenceClient()
    discovery = DeviceDiscovery.from_platform(_ready_device(state=state))
    with pytest.raises(BrowserComputeProtocolError, match=expected):
        discovery.local_base_url("retrieval")
    client.accept_discovery(_ready_device(state=state), required_capability="retrieval")
    assert client.session is None
