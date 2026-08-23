from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.routes import internal_debug
from app.core.config import settings
from app.main import app


client = TestClient(app)


def test_internal_debug_routes_are_disableable(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG_UI_ENABLED", False)
    response = client.get("/internal/debug/documents")
    assert response.status_code == 404
    assert response.json()["detail"] == "Debug endpoints are disabled"


def test_debug_request_forbids_generation_and_retrieval_overrides(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG_UI_ENABLED", True)
    monkeypatch.setattr(settings, "APP_ENV", "test")
    response = client.post(
        "/internal/debug/rag",
        json={"query_text": "q", "temperature": 0.7},
    )
    assert response.status_code == 422


def test_debug_route_returns_typed_trace_without_secrets_or_prompt(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG_UI_ENABLED", True)
    monkeypatch.setattr(settings, "APP_ENV", "test")

    class FakeDebugService:
        def __init__(self, db, **_kwargs):
            pass

        async def run(self, request_id, payload):
            return {
                "request_id": request_id,
                "query_text": payload.query_text,
                "document_ids": [],
                "retrieval": {
                    "dense_candidates": [], "lexical_candidates": [], "final_candidates": [],
                    "dense_candidate_count": 0, "lexical_candidate_count": 0,
                    "overlap_count": 0, "lexical_mode": "NO_LEXICAL_MATCH",
                    "timings_ms": {},
                },
                "context": {
                    "candidate_count": 0, "duplicate_count": 0, "selected_count": 0,
                    "dropped_count": 0, "context_token_count": 0,
                    "context_budget_tokens": 4096, "budget_utilization_percent": 0,
                    "budget_exhausted": False, "stop_reason": "NONE", "selected_evidence": [],
                },
                "generation": {
                    "status": "INSUFFICIENT_EVIDENCE",
                    "answerability_status": "INSUFFICIENT_EVIDENCE",
                    "answerability_validation": "PASS",
                    "answer_text": "Bằng chứng không đủ.", "citations": [],
                    "invalid_citations": [], "citation_validation": "PASS",
                    "model_id": "qwen3.5:9b", "prompt_version": "legal-rag-v2",
                    "finish_reason": None, "usage": None, "prompt_token_count": 0,
                    "context_token_count": 0, "generation_ms": 0,
                    "time_to_first_token_ms": None,
                },
                "timings_ms": {"total_ms": 1}, "expected": None, "diagnosis": None,
            }

    monkeypatch.setattr(internal_debug, "DebugRagService", FakeDebugService)
    response = client.post(
        "/internal/debug/rag",
        headers={"X-Request-ID": "debug-123"},
        json={"query_text": "Câu hỏi chẩn đoán"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "debug-123"
    serialized = response.text.lower()
    for forbidden in ("api_key", "authorization", "database_url", "system_prompt", "reasoning"):
        assert forbidden not in serialized
