import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient
from redis import Redis

from app.core.config import settings
from app.core.exceptions import InvalidDocumentError
from app.main import app
from app.pdf.extractor import PDFExtractor
from app.pdf.validator import validate_and_hash_pdf
from app.security.rate_limits import GenerationAdmissionController, LoginRateLimiter


def _pdf(text: str = "Văn bản pháp luật thử nghiệm") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    payload = doc.tobytes()
    doc.close()
    return payload


def test_login_rate_limit_is_atomic_distributed_and_returns_429(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_LOGIN_BURST", 3)
    monkeypatch.setattr(settings, "AUTH_LOGIN_RATE_PER_MINUTE", 3)
    client = TestClient(app)
    statuses = [
        client.post("/api/v1/auth/login", json={"email": "security-missing@example.invalid", "password": "wrong password"}).status_code
        for _ in range(4)
    ]
    assert statuses == [401, 401, 401, 429]

    redis = Redis.from_url(settings.REDIS_URL)
    keys = list(redis.scan_iter(match=b"security:v1:login:*"))
    assert len(keys) == 2
    assert all(b"security-missing" not in key for key in keys)


def test_generation_admission_user_global_rate_release_and_stale_recovery(monkeypatch):
    namespace = f"security:test:generation:{uuid.uuid4()}"
    controller = GenerationAdmissionController(namespace=namespace)
    monkeypatch.setattr(settings, "CHAT_GENERATION_RATE_PER_MINUTE", 600)
    monkeypatch.setattr(settings, "CHAT_GENERATION_BURST", 10)
    monkeypatch.setattr(settings, "CHAT_MAX_ACTIVE_GENERATIONS_PER_USER", 1)
    monkeypatch.setattr(settings, "CHAT_MAX_GLOBAL_GENERATIONS", 1)
    monkeypatch.setattr(settings, "CHAT_GENERATION_LEASE_TTL_SECONDS", 1)

    allowed, first = controller.acquire("alice")
    assert allowed.allowed and first is not None
    same_user, _ = controller.acquire("alice")
    other_user, _ = controller.acquire("bob")
    assert (same_user.allowed, same_user.reason) == (False, "USER_GENERATION_ACTIVE")
    assert (other_user.allowed, other_user.reason) == (False, "GLOBAL_GENERATION_ACTIVE")
    controller.release(first)
    allowed_again, second = controller.acquire("bob")
    assert allowed_again.allowed

    # Simulate process death: no release. Expired sorted-set leases are removed
    # atomically by the next acquire.
    time.sleep(1.05)
    recovered, recovered_lease = controller.acquire("alice")
    assert recovered.allowed
    controller.release(second)
    controller.release(recovered_lease)


def test_pdf_admission_rejects_mime_filename_structure_encryption_and_page_cap(monkeypatch):
    valid = _pdf()
    validate_and_hash_pdf(valid, "hợp-lệ.pdf", "application/pdf")
    for filename in ("../escape.pdf", "..\\escape.pdf", "bad\x00.pdf", "a" * 256 + ".pdf"):
        with pytest.raises(InvalidDocumentError):
            validate_and_hash_pdf(valid, filename, "application/pdf")
    with pytest.raises(InvalidDocumentError, match="content type"):
        validate_and_hash_pdf(valid, "valid.pdf", "text/plain")
    with pytest.raises(InvalidDocumentError, match="content type"):
        validate_and_hash_pdf(valid, "valid.pdf", "")
    with pytest.raises(InvalidDocumentError, match="Malformed|truncated"):
        validate_and_hash_pdf(b"%PDF-1.7\ntruncated", "broken.pdf", "application/pdf")

    encrypted = pymupdf.open()
    encrypted.new_page().insert_text((72, 72), "secret")
    encrypted_bytes = encrypted.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw="user-password",
    )
    encrypted.close()
    with pytest.raises(InvalidDocumentError, match="password-protected"):
        validate_and_hash_pdf(encrypted_bytes, "encrypted.pdf", "application/pdf")

    monkeypatch.setattr(settings, "PDF_MAX_PAGES", 1)
    many = pymupdf.open()
    many.new_page(); many.new_page()
    many_bytes = many.tobytes(); many.close()
    with pytest.raises(InvalidDocumentError, match="page count"):
        validate_and_hash_pdf(many_bytes, "many.pdf", "application/pdf")


def test_pdf_external_uri_is_not_fetched_by_extraction():
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(204); self.end_headers()

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72), "External reference")
        page.insert_link({
            "kind": pymupdf.LINK_URI,
            "from": pymupdf.Rect(70, 50, 250, 90),
            "uri": f"http://127.0.0.1:{server.server_port}/ssrf-canary",
        })
        payload = doc.tobytes(); doc.close()
        assert list(PDFExtractor.extract_pages(payload))[0]["raw_text"].startswith("External reference")
        time.sleep(0.1)
        assert hits == []
    finally:
        server.shutdown(); server.server_close(); thread.join(2)


def test_compressed_repetitive_pdf_is_stopped_by_extracted_text_cap(monkeypatch):
    document = pymupdf.open(); page = document.new_page()
    for index in range(200):
        page.insert_text((40, 40 + (index % 20) * 8), "REPETITIVE-COMPRESSED-CONTENT-" * 8, fontsize=6)
    payload = document.tobytes(deflate=True); document.close()
    monkeypatch.setattr(settings, "PDF_MAX_PAGE_EXTRACTED_CHARS", 100)
    with pytest.raises(InvalidDocumentError, match="extracted-text safety limit"):
        list(PDFExtractor.extract_pages(payload))


def test_security_headers_request_size_and_request_id_sanitization(monkeypatch):
    client = TestClient(app)
    response = client.get("/health", headers={"X-Request-ID": "bad request id value"})
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "strict-transport-security" not in response.headers
    assert response.headers["x-request-id"] != "bad request id value"

    monkeypatch.setattr(settings, "REQUEST_MAX_JSON_BYTES", 64)
    oversized = client.post("/retrieve", content=b"{" + b" " * 100 + b"}", headers={"Content-Type": "application/json"})
    assert oversized.status_code == 413
    assert oversized.json()["detail"]["error_code"] == "REQUEST_TOO_LARGE"


def test_csrf_mutation_matrix_and_credentialed_cors_policy():
    client = TestClient(app)
    hostile = {"Origin": "https://evil.example"}
    random_id = str(uuid.uuid4())
    attacks = [
        client.post("/documents", headers=hostile, files={"file": ("x.pdf", _pdf(), "application/pdf")}),
        client.delete(f"/documents/{random_id}", headers=hostile),
        client.patch(f"/api/v1/chat/sessions/{random_id}", headers=hostile, json={"title": "stolen"}),
        client.delete(f"/api/v1/chat/sessions/{random_id}", headers=hostile),
        client.post("/api/v1/auth/change-password", headers=hostile, json={"current_password": "x", "new_password": "y"}),
        client.request("DELETE", "/api/v1/auth/account", headers=hostile, json={"password": "x"}),
        client.post(f"/api/v1/admin/documents/{random_id}/global-access", headers=hostile),
    ]
    assert all(response.status_code == 403 for response in attacks)
    assert all(response.json()["detail"]["error_code"] == "UNTRUSTED_ORIGIN" for response in attacks)

    allowed = client.options(
        "/api/v1/auth/login",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"},
    )
    evil = client.options(
        "/api/v1/auth/login",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"},
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert allowed.headers["access-control-allow-credentials"] == "true"
    assert evil.status_code == 400 and "access-control-allow-origin" not in evil.headers
    assert allowed.headers["access-control-allow-origin"] != "*"


def test_malformed_inputs_and_dependency_failures_return_sanitized_errors(monkeypatch):
    client = TestClient(app)
    probes = [
        client.get("/documents/not-a-uuid"),
        client.get("/indexing-jobs/not-a-uuid"),
        client.post("/retrieve", content=b'{"query_text":', headers={"Content-Type": "application/json"}),
        client.post("/documents", files={"file": ("broken.pdf", b"%PDF-1.7\ntruncated", "application/pdf")}),
    ]
    assert all(response.status_code < 500 for response in probes)
    forbidden = ("postgresql://", "redis://", "minio:", "/app/", "traceback", "RagDbSec", "RagMinioSec")
    assert all(not any(marker.casefold() in response.text.casefold() for marker in forbidden) for response in probes)


def test_compose_exposure_worker_limits_and_legacy_authorization_static_contract():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    for port in ("5432", "6379", "9000", "9001", "8001", "5173"):
        assert f'127.0.0.1:{port}:' in compose
    assert "internal: true" in compose
    assert "mem_limit:" in compose and "pids_limit:" in compose and "restart: unless-stopped" in compose

    authorization_occurrences = []
    for path in Path("app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "Document.user_id" in text or "document.user_id" in text or "documents.user_id" in text:
            authorization_occurrences.append(str(path))
    assert authorization_occurrences == []
