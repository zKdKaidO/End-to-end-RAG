from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.context.service import ContextBuilderService
from app.generation.client import LLMResult
from app.generation.exceptions import GenerationDependencyError, GenerationTimeoutError
from app.generation.profile import GenerationProfile
from app.generation.schemas import CitationValidation, Usage
from app.local_compute.api import create_local_compute_app
from app.local_compute import api as local_api
from app.local_compute.errors import LocalComputeError, LocalComputeErrorCode
from app.local_compute.generation import (
    GenerationProviderType,
    GenerationRouter,
    LocalAnswerService,
    LocalGenerationAvailability,
    LocalGenerationProvider,
    LocalGenerationState,
)
from app.local_compute.runtime import LocalComputeRuntime
from app.local_compute.settings import LocalComputeSettings, PRODUCT_ORIGIN
from tests.context_doubles import CharacterTokenCounter
from tests.generation_doubles import FixedPromptCounter


def profile() -> GenerationProfile:
    return GenerationProfile(
        provider="ollama",
        model_id="qwen3.5:9b",
        tokenizer_provider="test",
        tokenizer_id="test",
        model_context_limit=1_000,
        context_budget_tokens=500,
        max_output_tokens=50,
        prompt_token_safety_margin=5,
        thinking=False,
        temperature=0,
        top_p=0.9,
        top_k=20,
        prompt_version="legal-rag-v2",
        request_timeout_seconds=10,
    )


class FakeOllamaClient:
    def __init__(self, *, text="[STATUS: ANSWERABLE]\nNội dung [S1]", health_error=None, generate_error=None):
        self.text = text
        self.health_error = health_error
        self.generate_error = generate_error
        self.health_calls = 0
        self.generate_calls = 0
        self.closed = False

    async def health(self, _profile):
        self.health_calls += 1
        if self.health_error:
            raise self.health_error

    async def generate(self, _messages, _profile):
        self.generate_calls += 1
        if self.generate_error:
            raise self.generate_error
        return LLMResult(self.text, "stop", Usage(input_tokens=20, output_tokens=5, total_tokens=25))

    async def close(self):
        self.closed = True


class FakeLocalRetrieval:
    def __init__(self):
        self.calls = 0

    def query_document_set_with_diagnostics(self, query_text, document_ids):
        self.calls += 1
        assert query_text == "Mức phí là bao nhiêu?"
        assert document_ids == [str(UUID(int=2))]
        return [
            {
                "chunk_id": str(UUID(int=1)),
                "document_id": str(UUID(int=2)),
                "artifact_id": str(UUID(int=3)),
                "content_text": "Mức phí là 10 phần trăm.",
                "metadata_json": {"title": "Văn bản thật"},
                "provenance_json": {"document_id": str(UUID(int=2)), "page_start": 1},
                "dense_score": 0.9,
                "dense_rank": 1,
                "lexical_score": None,
                "lexical_rank": None,
                "fusion_score": 0.02,
                "retrieval_final_rank": 1,
                "final_rank": 1,
                "context_candidate_order": 1,
                "candidate_origin": "RETRIEVAL",
                "legal_unit_id": str(UUID(int=4)),
                "hierarchy_relation": None,
                "hierarchy_depth": 0,
                "anchor_chunk_id": None,
                "anchor_legal_unit_id": None,
                "anchor_retrieval_final_rank": None,
                "hierarchy_anchor_references": [],
            }
        ], {"status": "NO_EXPANSION", "children_added": 0}


def provider(client: FakeOllamaClient) -> LocalGenerationProvider:
    return LocalGenerationProvider(profile(), "http://127.0.0.1:11434", client=client)


def service(client: FakeOllamaClient) -> tuple[LocalAnswerService, FakeLocalRetrieval]:
    retrieval = FakeLocalRetrieval()
    subject = LocalAnswerService(
        LocalComputeSettings(data_root=__import__("pathlib").Path("unused")),
        None,
        GenerationRouter(provider(client)),
        profile=profile(),
        retrieval_store=retrieval,
        context_builder=ContextBuilderService(CharacterTokenCounter()),
        prompt_counter=FixedPromptCounter(100),
    )
    return subject, retrieval


@pytest.mark.asyncio
async def test_local_provider_reports_actual_availability_and_metadata():
    client = FakeOllamaClient()
    subject = provider(client)
    availability = await subject.availability()
    assert availability.state == LocalGenerationState.READY
    assert subject.model_info() == {"provider": "LOCAL", "model_id": "qwen3.5:9b"}
    assert await subject.cancel() is False
    await subject.close()
    assert client.closed is True


@pytest.mark.asyncio
async def test_model_unavailable_timeout_and_nonlocal_endpoint_fail_honestly():
    missing = provider(FakeOllamaClient(health_error=GenerationDependencyError("x", "MODEL_UNAVAILABLE", "missing")))
    assert (await missing.availability()).state == LocalGenerationState.MODEL_UNAVAILABLE
    with pytest.raises(LocalComputeError) as missing_error:
        await missing.generate([])
    assert missing_error.value.code == LocalComputeErrorCode.MODEL_UNAVAILABLE

    timeout = provider(FakeOllamaClient(generate_error=GenerationTimeoutError("x", "PROVIDER_TIMEOUT", "slow")))
    with pytest.raises(LocalComputeError) as timeout_error:
        await timeout.generate([])
    assert timeout_error.value.code == LocalComputeErrorCode.GENERATION_TIMEOUT

    with pytest.raises(LocalComputeError):
        LocalGenerationProvider(profile(), "https://example.test")
    development = LocalGenerationProvider(
        profile(), "http://host.docker.internal:11434", development_mode=True, client=FakeOllamaClient()
    )
    assert development.endpoint == "http://host.docker.internal:11434"


def test_router_has_no_user_or_platform_cloud_fallback():
    router = GenerationRouter(provider(FakeOllamaClient()))
    assert router.provider_for().provider_type == GenerationProviderType.LOCAL
    for provider_type in (GenerationProviderType.USER_CLOUD, GenerationProviderType.PLATFORM_CLOUD):
        with pytest.raises(LocalComputeError) as exc_info:
            router.provider_for(provider_type)
        expected = (
            LocalComputeErrorCode.PLATFORM_CLOUD_DISABLED
            if provider_type == GenerationProviderType.PLATFORM_CLOUD
            else LocalComputeErrorCode.CAPABILITY_UNAVAILABLE
        )
        assert exc_info.value.code == expected


@pytest.mark.asyncio
async def test_local_answer_uses_canonical_prompt_finalization_and_source_mapping():
    subject, retrieval = service(FakeOllamaClient())
    response = await subject.answer(
        request_id="local-answer-1",
        query_text="Mức phí là bao nhiêu?",
        document_ids=[str(UUID(int=2))],
    )
    assert retrieval.calls == 1
    assert response.provider == GenerationProviderType.LOCAL
    assert response.model_id == "qwen3.5:9b"
    assert response.result.answer_text == "Nội dung [S1]"
    assert response.result.citations[0].chunk_id == str(UUID(int=1))
    assert response.result.citations[0].provenance_json["page_start"] == 1
    assert response.result.citation_validation == CitationValidation.PASS
    assert response.timings["prompt_token_count"] == 100.0


@pytest.mark.asyncio
async def test_local_answer_preserves_unknown_citation_and_malformed_status_handling():
    unknown, _ = service(FakeOllamaClient(text="[STATUS: ANSWERABLE]\nKhông đúng [S99]"))
    unknown_response = await unknown.answer(
        request_id="local-answer-2", query_text="Mức phí là bao nhiêu?", document_ids=[str(UUID(int=2))]
    )
    assert unknown_response.result.invalid_citations == ["S99"]
    assert unknown_response.result.citations == []

    malformed, _ = service(FakeOllamaClient(text="Trả lời không đánh dấu [S1]"))
    malformed_response = await malformed.answer(
        request_id="local-answer-3", query_text="Mức phí là bao nhiêu?", document_ids=[str(UUID(int=2))]
    )
    assert malformed_response.result.answerability_validation.value == "ANSWERABILITY_STATUS_MISSING"
    assert malformed_response.result.status.value == "COMPLETED_WITH_WARNINGS"


@pytest.mark.asyncio
async def test_local_failure_never_calls_a_second_provider():
    client = FakeOllamaClient(health_error=GenerationDependencyError("x", "PROVIDER_UNAVAILABLE", "offline"))
    subject, _ = service(client)
    with pytest.raises(LocalComputeError) as exc_info:
        await subject.answer(
            request_id="local-answer-4", query_text="Mức phí là bao nhiêu?", document_ids=[str(UUID(int=2))]
        )
    assert exc_info.value.code == LocalComputeErrorCode.GENERATION_UNAVAILABLE
    assert client.generate_calls == 0


@pytest.mark.asyncio
async def test_capability_endpoint_reports_model_state_without_affecting_retrieval(tmp_path):
    runtime = LocalComputeRuntime(
        LocalComputeSettings(data_root=tmp_path / "Compute", development_mode=True, development_origins=("http://localhost:5173",))
    )
    runtime.start()
    runtime._generation_router = GenerationRouter(provider(FakeOllamaClient()))
    try:
        client = TestClient(create_local_compute_app(runtime))
        session = client.post("/v1/sessions", headers={"Origin": PRODUCT_ORIGIN, "X-ZKD-Local-Grant": "development-test-grant"}).json()
        import hashlib, hmac, time, uuid

        body = b""
        timestamp = str(int(time.time()))
        nonce = str(uuid.uuid4())
        payload = "|".join(("GET", "/v1/capabilities", timestamp, nonce, hashlib.sha256(body).hexdigest())).encode()
        headers = {
            "Origin": PRODUCT_ORIGIN,
            "X-ZKD-Local-Session": session["local_session_id"],
            "X-ZKD-Timestamp": timestamp,
            "X-ZKD-Nonce": nonce,
            "X-ZKD-MAC": hmac.new(session["session_key"].encode(), payload, hashlib.sha256).hexdigest(),
            "X-ZKD-Protocol-Version": "zkd-compute-v1",
        }
        response = client.get("/v1/capabilities", headers=headers)
        assert response.status_code == 200
        assert response.json()["capabilities"]["generation"] == "READY"
        assert response.json()["capabilities"]["retrieval"] == "READY"
    finally:
        runtime.shutdown()


def test_answer_protocol_operation_is_additive_and_authenticated(tmp_path, monkeypatch):
    runtime = LocalComputeRuntime(
        LocalComputeSettings(data_root=tmp_path / "Compute", development_mode=True, development_origins=("http://localhost:5173",))
    )
    runtime.start()

    class FakeResponse:
        def as_dict(self):
            return {"provider": "LOCAL", "model_id": "qwen3.5:9b", "result": {"status": "COMPLETED"}, "hierarchy": {}, "timings": {}}

    class FakeAnswerService:
        async def answer(self, *, request_id, query_text, document_ids):
            assert request_id
            assert query_text == "Câu hỏi"
            assert document_ids is None
            return FakeResponse()

        def __init__(self, *_args):
            pass

    monkeypatch.setattr(local_api, "LocalAnswerService", FakeAnswerService)
    try:
        client = TestClient(create_local_compute_app(runtime))
        session = client.post("/v1/sessions", headers={"Origin": PRODUCT_ORIGIN, "X-ZKD-Local-Grant": "development-test-grant"}).json()
        body = json.dumps({"query_text": "Câu hỏi"}, ensure_ascii=False).encode()
        timestamp = str(int(time.time()))
        nonce = str(uuid.uuid4())
        signed = "|".join(("POST", "/v1/answers", timestamp, nonce, hashlib.sha256(body).hexdigest())).encode()
        headers = {
            "Origin": PRODUCT_ORIGIN,
            "Content-Type": "application/json",
            "X-ZKD-Local-Session": session["local_session_id"],
            "X-ZKD-Timestamp": timestamp,
            "X-ZKD-Nonce": nonce,
            "X-ZKD-MAC": hmac.new(session["session_key"].encode(), signed, hashlib.sha256).hexdigest(),
            "X-ZKD-Protocol-Version": "zkd-compute-v1",
        }
        response = client.post("/v1/answers", content=body, headers=headers)
        assert response.status_code == 200
        assert response.json()["provider"] == "LOCAL"
        assert response.json()["result"]["status"] == "COMPLETED"
    finally:
        runtime.shutdown()
