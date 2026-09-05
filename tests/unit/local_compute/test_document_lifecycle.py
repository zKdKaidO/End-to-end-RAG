from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
import uuid
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings as server_settings
from app.local_compute.api import create_local_compute_app
from app.local_compute.documents import LocalDocumentStore
from app.local_compute.errors import LocalComputeError, LocalComputeErrorCode
from app.local_compute.indexing import LocalIndexService
from app.local_compute.preparation import LocalPreparationService
from app.local_compute.retrieval import LocalRetrievalStore
from app.local_compute.runtime import LocalComputeRuntime
from app.local_compute.settings import PRODUCT_ORIGIN, LocalComputeSettings


def _pdf_bytes(text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    result = document.tobytes()
    document.close()
    return result


@pytest.fixture
def runtime(tmp_path):
    instance = LocalComputeRuntime(
        LocalComputeSettings(
            data_root=tmp_path / "Compute",
            development_mode=True,
            development_origins=("http://localhost:5173",),
            control_auto_start=False,
            embedding_model_cache_dir=Path(
                server_settings.EMBEDDING_MODEL_CACHE_DIR
            ),
        )
    )
    instance.start()
    yield instance
    instance.shutdown()


def _session(client: TestClient) -> dict:
    response = client.post("/v1/sessions", headers={"Origin": PRODUCT_ORIGIN, "X-ZKD-Local-Grant": "development-test-grant"})
    assert response.status_code == 200, response.text
    return response.json()


def _headers(session: dict, method: str, path: str, body: bytes = b"", *, origin: str = PRODUCT_ORIGIN, nonce: str | None = None, timestamp: int | None = None) -> dict[str, str]:
    timestamp_text = str(int(time.time()) if timestamp is None else timestamp)
    request_nonce = nonce or str(uuid.uuid4())
    transcript = "|".join((method, path, timestamp_text, request_nonce, hashlib.sha256(body).hexdigest())).encode()
    return {
        "Origin": origin,
        "X-ZKD-Local-Session": session["local_session_id"],
        "X-ZKD-Timestamp": timestamp_text,
        "X-ZKD-Nonce": request_nonce,
        "X-ZKD-MAC": hmac.new(session["session_key"].encode(), transcript, hashlib.sha256).hexdigest(),
        "X-ZKD-Protocol-Version": "zkd-compute-v1",
    }


def _accept(runtime, document_id: str, text: str = "Điều 1. Doanh nghiệp phải thực hiện nghĩa vụ."):
    return LocalDocumentStore(runtime.settings, runtime.catalog).accept_document(document_id, [_pdf_bytes(text)], "legal.pdf", "application/pdf")


def test_authenticated_delete_and_local_list_hide_paths_and_content(runtime):
    client = TestClient(create_local_compute_app(runtime))
    session = _session(client)
    document_id = str(uuid.uuid4())
    _accept(runtime, document_id)

    listing = client.get("/v1/documents", headers=_headers(session, "GET", "/v1/documents"))
    assert listing.status_code == 200
    item = listing.json()["documents"][0]
    assert item["document_id"] == document_id and item["preparation_state"] == "ACCEPTED"
    assert {"source_relative_path", "content_sha256", "content_text", "vector", "embedding"}.isdisjoint(item)

    path = f"/v1/documents/{document_id}"
    deleted = client.delete(path, headers=_headers(session, "DELETE", path))
    assert deleted.status_code == 200 and deleted.json()["state"] == "DELETED"
    assert client.get("/v1/documents", headers=_headers(session, "GET", "/v1/documents")).json()["documents"] == []
    assert not (runtime.settings.documents_path / document_id).exists()
    assert not (runtime.settings.artifacts_path / document_id).exists()
    assert LocalDocumentStore(runtime.settings, runtime.catalog).get(document_id) is None
    pending = runtime.catalog.pending_control_manifests()
    assert pending and pending[0]["payload"] == {"document_id": document_id, "preparation_state": "DELETED", "index_state": "DELETED", "local_availability": "DELETED", "chunk_count": 0, "artifact_id": None, "artifact_version": None, "artifact_profile_fingerprint": None}


def test_delete_auth_rejections_have_zero_side_effects(runtime):
    client = TestClient(create_local_compute_app(runtime))
    session = _session(client)
    document_id = str(uuid.uuid4())
    _accept(runtime, document_id)
    path = f"/v1/documents/{document_id}"
    cases = [
        ({"Origin": PRODUCT_ORIGIN}, 401),
        ({**_headers(session, "DELETE", path), "X-ZKD-MAC": "0" * 64}, 401),
        (_headers(session, "DELETE", path, origin="https://evil.example"), 403),
        (_headers(session, "DELETE", path, timestamp=int(time.time()) - 1000), 401),
    ]
    for headers, expected in cases:
        assert client.delete(path, headers=headers).status_code == expected
        assert LocalDocumentStore(runtime.settings, runtime.catalog).get(document_id) is not None
    runtime.sessions._sessions[session["local_session_id"]].allowed_operations = frozenset({"retrieval"})
    assert client.delete(path, headers=_headers(session, "DELETE", path)).status_code == 403
    assert LocalDocumentStore(runtime.settings, runtime.catalog).get(document_id) is not None
    runtime.sessions._sessions[session["local_session_id"]].allowed_operations = frozenset({"documents"})
    replay = _headers(session, "DELETE", path, nonce="delete-replay")
    assert client.delete(path, headers=replay).status_code == 200
    assert client.delete(path, headers=replay).status_code == 409
    assert client.delete(path, headers=_headers(session, "DELETE", path)).status_code == 404


def test_failed_and_orphaned_local_documents_can_be_deleted(runtime):
    store = LocalDocumentStore(runtime.settings, runtime.catalog)
    failed_id = str(uuid.uuid4())
    _accept(runtime, failed_id, "")
    with pytest.raises(LocalComputeError):
        LocalPreparationService(runtime.settings, runtime.catalog).prepare(failed_id)
    assert store.get(failed_id)["preparation_state"] == "FAILED"
    assert store.list_documents()[0]["preparation_state"] == "FAILED"
    assert store.delete_document(failed_id)["state"] == "DELETED"

    orphan_id = str(uuid.uuid4())
    _accept(runtime, orphan_id)
    (runtime.settings.documents_path / orphan_id / "source.pdf").unlink()
    (runtime.settings.artifacts_path / orphan_id / "partial").mkdir(parents=True)
    assert store.delete_document(orphan_id)["state"] == "DELETED"
    assert store.get(orphan_id) is None


def test_indexed_document_is_not_retrievable_after_authorized_delete(runtime):
    document_id = str(uuid.uuid4())
    _accept(runtime, document_id)
    LocalPreparationService(runtime.settings, runtime.catalog).prepare(document_id)
    LocalIndexService(runtime.settings, runtime.catalog).index_document(document_id)
    retrieval = LocalRetrievalStore(runtime.settings, runtime.catalog)
    # The frozen local retrieval contract treats omitted/null and [] as all
    # queryable local documents. The browser product layer must therefore
    # reject an empty explicit selection before it reaches this route.
    assert retrieval.query_document_set("doanh nghiệp")
    assert retrieval.query_document_set("doanh nghiệp", [])
    assert retrieval.query_document_set("doanh nghiệp", [document_id])
    LocalDocumentStore(runtime.settings, runtime.catalog).delete_document(document_id)
    with pytest.raises(LocalComputeError) as blocked:
        retrieval.query_document_set("doanh nghiệp", [document_id])
    assert blocked.value.code == LocalComputeErrorCode.DOCUMENT_NOT_FOUND


def test_delete_serializes_with_lifecycle_and_tombstone_replaces_prior_manifest(runtime):
    document_id = str(uuid.uuid4())
    _accept(runtime, document_id)
    runtime.catalog.enqueue_control_manifest({"document_id": document_id, "preparation_state": "INDEX_READY", "index_state": "INDEX_READY", "local_availability": "AVAILABLE", "chunk_count": 1, "artifact_id": str(uuid.uuid4()), "artifact_version": "v1", "artifact_profile_fingerprint": "a" * 64}, int(time.time()))
    LocalDocumentStore(runtime.settings, runtime.catalog).delete_document(document_id)
    pending = runtime.catalog.pending_control_manifests()
    assert len(pending) == 1 and pending[0]["payload"]["local_availability"] == "DELETED" and pending[0]["revision"] == 2
    with pytest.raises(LocalComputeError) as absent:
        LocalPreparationService(runtime.settings, runtime.catalog).prepare(document_id)
    assert absent.value.code == LocalComputeErrorCode.DOCUMENT_NOT_FOUND


def test_delete_waits_for_active_preparation_then_prevents_resurrection(runtime, monkeypatch):
    document_id = str(uuid.uuid4())
    _accept(runtime, document_id)
    service = LocalPreparationService(runtime.settings, runtime.catalog)
    started, release, deleted = threading.Event(), threading.Event(), threading.Event()
    original_persist = service._persist

    def blocking_persist(*args, **kwargs):
        started.set()
        assert release.wait(timeout=10)
        return original_persist(*args, **kwargs)

    monkeypatch.setattr(service, "_persist", blocking_persist)
    preparation_error: list[Exception] = []

    def prepare():
        try:
            service.prepare(document_id)
        except Exception as exc:  # pragma: no cover - assertion below preserves the real failure
            preparation_error.append(exc)

    def delete():
        LocalDocumentStore(runtime.settings, runtime.catalog).delete_document(document_id)
        deleted.set()

    preparing = threading.Thread(target=prepare)
    preparing.start()
    assert started.wait(timeout=10)
    deleting = threading.Thread(target=delete)
    deleting.start()
    assert not deleted.is_set()
    release.set()
    preparing.join(timeout=15)
    deleting.join(timeout=15)
    assert not preparation_error and deleted.is_set()
    assert LocalDocumentStore(runtime.settings, runtime.catalog).get(document_id) is None
    assert not (runtime.settings.artifacts_path / document_id).exists()
