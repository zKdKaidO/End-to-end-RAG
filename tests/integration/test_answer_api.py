from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.routes.answer import get_answer_service
from app.generation.exceptions import GenerationDependencyError, GenerationTimeoutError, GenerationValidationError
from app.generation.schemas import CitationValidation, GenerationResult, GenerationStatus
from app.main import app


client = TestClient(app)


def result(request_id="api-request"):
    return GenerationResult(
        request_id=request_id,
        status=GenerationStatus.COMPLETED,
        answer_text="Trả lời [S1]",
        citations=[],
        invalid_citations=[],
        citation_validation=CitationValidation.PASS,
        model_id="qwen3.5:9b",
        prompt_version="legal-rag-v1",
        finish_reason="stop",
        usage=None,
    )


class FakeAnswerService:
    def __init__(self, error=None, stream_error=None, prompt_version="legal-rag-v1"):
        self.error = error
        self.stream_error = stream_error
        self.request = None
        self.profile = SimpleNamespace(model_id="qwen3.5:9b", prompt_version=prompt_version)

    async def answer(self, request_id, request):
        self.request = request
        if not request.query_text.strip():
            raise GenerationValidationError("VALIDATE_REQUEST", "INVALID_QUERY", "empty")
        if self.error:
            raise self.error
        return result(request_id)

    async def prepare(self, request_id, request):
        self.request = request
        if not request.query_text.strip():
            raise GenerationValidationError("VALIDATE_REQUEST", "INVALID_QUERY", "empty")
        if self.error:
            raise self.error
        return SimpleNamespace(request_id=request_id)

    async def stream_prepared(self, prepared):
        yield "delta", "Trả lời "
        if self.stream_error:
            raise self.stream_error
        yield "delta", "[S1]"
        yield "done", result(prepared.request_id)

    async def check_provider(self, prepared):
        if self.error:
            raise self.error


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def override(service):
    app.dependency_overrides[get_answer_service] = lambda: service


def test_answer_contract_request_id_and_forbidden_client_controls():
    service = FakeAnswerService()
    override(service)
    response = client.post(
        "/answer",
        headers={"X-Request-ID": "answer-123"},
        json={"query_text": "Quyền gì?", "document_ids": None},
    )
    assert response.status_code == 200
    assert response.json()["request_id"] == "answer-123"
    assert response.headers["X-Request-ID"] == "answer-123"
    assert set(service.request.model_fields_set) == {"query_text", "document_ids"}

    for forbidden in ("model", "temperature", "top_k", "system_prompt", "max_output_tokens", "prompt_version"):
        assert client.post("/answer", json={"query_text": "q", forbidden: 1}).status_code == 400


@pytest.mark.parametrize("query", ["", "   "])
def test_answer_empty_query_is_400(query):
    override(FakeAnswerService())
    response = client.post("/answer", json={"query_text": query})
    assert response.status_code == 400


def test_answer_provider_failure_http_mapping():
    cases = [
        (GenerationDependencyError("LLM_REQUEST", "PROVIDER_UNAVAILABLE", "unavailable"), 503),
        (GenerationTimeoutError("LLM_REQUEST", "PROVIDER_TIMEOUT", "timeout"), 504),
    ]
    for error, expected in cases:
        override(FakeAnswerService(error=error))
        response = client.post("/answer", json={"query_text": "q"})
        assert response.status_code == expected
        assert response.json()["detail"]["stage"] == "LLM_REQUEST"


def test_stream_sse_start_delta_done_and_no_native_objects():
    override(FakeAnswerService())
    response = client.post("/answer/stream", json={"query_text": "q"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert body.index("event: start") < body.index("event: delta") < body.index("event: done")
    assert body.count("event: delta") == 2
    assert "prompt_eval_count" not in body and "eval_duration" not in body


def test_stream_reports_server_selected_v3_without_client_override():
    override(FakeAnswerService(prompt_version="legal-rag-v3"))
    response = client.post("/answer/stream", json={"query_text": "q"})
    assert response.status_code == 200
    assert '"prompt_version": "legal-rag-v3"' in response.text


def test_stream_failure_emits_error_and_never_done():
    override(FakeAnswerService(stream_error=GenerationDependencyError("STREAMING", "PROVIDER_STREAM_ERROR", "safe")))
    response = client.post("/answer/stream", json={"query_text": "q"})
    assert response.status_code == 200
    assert "event: start" in response.text
    assert "event: delta" in response.text
    assert "event: error" in response.text
    assert "event: done" not in response.text
