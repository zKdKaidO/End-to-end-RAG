from uuid import UUID

import pytest

from app.context.service import ContextBuilderService
from app.generation.exceptions import GenerationValidationError
from app.generation.profile import GenerationProfile
from app.generation.schemas import (
    AnswerabilityStatus,
    AnswerabilityValidation,
    AnswerRequest,
    CitationValidation,
    GenerationStatus,
)
from app.orchestration.answer_service import AnswerService
from tests.context_doubles import CharacterTokenCounter
from tests.generation_doubles import FakeLLMClient, FakeRetrievalService, FixedPromptCounter


def candidate():
    return {
        "chunk_id": str(UUID(int=1)), "document_id": str(UUID(int=2)),
        "content_text": "Doanh nghiệp được hưởng chính sách ưu đãi.",
        "metadata_json": {"title": "Luật thật"}, "provenance_json": {"page_start": 3},
        "dense_score": 0.8, "dense_rank": 1, "lexical_score": 0.5, "lexical_rank": 1,
        "fusion_score": 0.03, "final_rank": 1,
    }


def profile():
    return GenerationProfile(
        provider="ollama", model_id="qwen3.5:9b", tokenizer_provider="test", tokenizer_id="test",
        model_context_limit=1000, context_budget_tokens=500, max_output_tokens=50,
        prompt_token_safety_margin=5, thinking=False, temperature=0, top_p=.9, top_k=20,
        prompt_version="legal-rag-v2", request_timeout_seconds=10,
    )


def service(results, llm=None, prompt_tokens=100):
    llm = llm or FakeLLMClient()
    return AnswerService(
        FakeRetrievalService(results), llm, profile(),
        context_builder=ContextBuilderService(CharacterTokenCounter()),
        prompt_counter=FixedPromptCounter(prompt_tokens),
    ), llm


@pytest.mark.asyncio
async def test_nonstream_answer_maps_valid_citation_and_usage():
    subject, llm = service([candidate()])
    result = await subject.answer("req-1", AnswerRequest(query_text="Ưu đãi gì?"))
    assert result.status == GenerationStatus.COMPLETED
    assert result.citation_validation == CitationValidation.PASS
    assert result.citations[0].provenance_json == {"page_start": 3}
    assert result.usage.total_tokens == 108
    assert result.answerability_status == AnswerabilityStatus.ANSWERABLE
    assert result.answerability_validation == AnswerabilityValidation.PASS
    assert "[STATUS:" not in result.answer_text
    assert llm.generate_calls == 1


@pytest.mark.asyncio
async def test_no_evidence_short_circuits_provider():
    subject, llm = service([])
    result = await subject.answer("req-2", AnswerRequest(query_text="Không có dữ liệu"))
    assert result.status == GenerationStatus.INSUFFICIENT_EVIDENCE
    assert result.citations == []
    assert llm.generate_calls == 0 and llm.stream_calls == 0


@pytest.mark.asyncio
async def test_prompt_overflow_prevents_provider_call():
    subject, llm = service([candidate()], prompt_tokens=946)
    with pytest.raises(GenerationValidationError) as exc_info:
        await subject.answer("req-3", AnswerRequest(query_text="Câu hỏi dài"))
    assert exc_info.value.stage == "PROMPT_BUDGET_GUARD"
    assert exc_info.value.error_code == "QUERY_TOO_LONG"
    assert llm.generate_calls == 0


@pytest.mark.asyncio
async def test_prompt_exact_hard_limit_boundary_is_allowed():
    subject, llm = service([candidate()], prompt_tokens=945)
    result = await subject.answer("req-boundary", AnswerRequest(query_text="q"))
    assert result.status == GenerationStatus.COMPLETED
    assert llm.generate_calls == 1


@pytest.mark.asyncio
async def test_invalid_document_uuid_rejected_before_retrieval_or_provider():
    subject, llm = service([candidate()])
    with pytest.raises(GenerationValidationError):
        await subject.answer("req-invalid", AnswerRequest(query_text="q", document_ids=["bad-uuid"]))
    assert subject.retrieval_service.calls == 0
    assert llm.generate_calls == 0


@pytest.mark.asyncio
async def test_stream_accumulates_answer_and_emits_authoritative_done():
    subject, llm = service([candidate()])
    prepared = await subject.prepare("req-4", AnswerRequest(query_text="Ưu đãi gì?"))
    events = [event async for event in subject.stream_prepared(prepared)]
    assert [kind for kind, _ in events] == ["delta", "delta", "done"]
    done = events[-1][1]
    assert done.answer_text == "Nội dung trả lời [S1]"
    assert done.citation_validation == CitationValidation.PASS
    assert llm.stream_calls == 1 and llm.generate_calls == 0


@pytest.mark.asyncio
async def test_invalid_and_missing_citations_are_warnings_without_retry():
    invalid_llm = FakeLLMClient(text="[STATUS: ANSWERABLE]\nCó nguồn [S99]")
    invalid_service, _ = service([candidate()], invalid_llm)
    invalid = await invalid_service.answer("r", AnswerRequest(query_text="q"))
    assert invalid.status == GenerationStatus.COMPLETED_WITH_WARNINGS
    assert invalid.invalid_citations == ["S99"] and invalid.citations == []
    assert invalid_llm.generate_calls == 1

    missing_llm = FakeLLMClient(text="[STATUS: ANSWERABLE]\nKhông trích dẫn")
    missing_service, _ = service([candidate()], missing_llm)
    missing = await missing_service.answer("r", AnswerRequest(query_text="q"))
    assert missing.citation_validation == CitationValidation.MISSING_CITATIONS
    assert missing_llm.generate_calls == 1


@pytest.mark.asyncio
async def test_empty_provider_answer_and_unusual_finish_reason_are_preserved():
    empty_llm = FakeLLMClient(text="")

    async def unusual(messages, profile):
        empty_llm.generate_calls += 1
        from app.generation.client import LLMResult
        return LLMResult("", "length", None)

    empty_llm.generate = unusual
    subject, _ = service([candidate()], empty_llm)
    result = await subject.answer("r-empty", AnswerRequest(query_text="q"))
    assert result.answer_text == ""
    assert result.finish_reason == "length"
    assert result.status == GenerationStatus.COMPLETED_WITH_WARNINGS
    assert result.answerability_validation == AnswerabilityValidation.MISSING_STATUS


@pytest.mark.asyncio
async def test_authoritative_insufficient_marker_returns_standardized_result_without_citations_or_retry():
    llm = FakeLLMClient(text="[STATUS: INSUFFICIENT_EVIDENCE]\nNội dung không được công khai [S1]")
    subject, _ = service([candidate()], llm)
    result = await subject.answer("r-insufficient", AnswerRequest(query_text="q"))
    assert result.status == GenerationStatus.INSUFFICIENT_EVIDENCE
    assert result.answerability_status == AnswerabilityStatus.INSUFFICIENT_EVIDENCE
    assert result.answerability_validation == AnswerabilityValidation.PASS
    assert result.answer_text == "Bằng chứng được cung cấp không đủ để trả lời câu hỏi."
    assert result.citations == [] and result.invalid_citations == []
    assert "STATUS" not in result.answer_text
    assert llm.generate_calls == 1


@pytest.mark.asyncio
async def test_missing_or_malformed_status_fails_safely_without_semantic_guessing():
    for text, validation in (
        ("Bằng chứng không đủ thông tin.", AnswerabilityValidation.MISSING_STATUS),
        ("[STATUS ANSWERABLE]\nTrả lời [S1]", AnswerabilityValidation.MALFORMED_STATUS),
        ("[STATUS: UNKNOWN]\nTrả lời [S1]", AnswerabilityValidation.UNKNOWN_STATUS),
    ):
        llm = FakeLLMClient(text=text)
        subject, _ = service([candidate()], llm)
        result = await subject.answer("r-format", AnswerRequest(query_text="q"))
        assert result.status == GenerationStatus.COMPLETED_WITH_WARNINGS
        assert result.answerability_status is None
        assert result.answerability_validation == validation
        assert result.status != GenerationStatus.INSUFFICIENT_EVIDENCE
        assert "[STATUS" not in result.answer_text


@pytest.mark.asyncio
async def test_stream_buffers_and_strips_marker_and_stops_insufficient_upstream():
    answerable = FakeLLMClient(chunks=("[STATUS: ANS", "WERABLE]", "\nNội dung ", "[S1]"))
    subject, _ = service([candidate()], answerable)
    prepared = await subject.prepare("r-stream-answer", AnswerRequest(query_text="q"))
    events = [event async for event in subject.stream_prepared(prepared)]
    deltas = "".join(value for kind, value in events if kind == "delta")
    assert deltas == "Nội dung [S1]"
    assert "STATUS" not in deltas
    assert events[-1][1].answer_text == deltas

    state = {"closed": False, "after_marker": False}

    class InsufficientStreamClient(FakeLLMClient):
        async def stream(self, messages, profile):
            self.stream_calls += 1
            try:
                yield __import__("app.generation.client", fromlist=["LLMStreamChunk"]).LLMStreamChunk(
                    text="[STATUS: INSUFFICIENT_EVIDENCE]"
                )
                state["after_marker"] = True
                yield __import__("app.generation.client", fromlist=["LLMStreamChunk"]).LLMStreamChunk(
                    text="unsupported"
                )
            finally:
                state["closed"] = True

    insufficient_llm = InsufficientStreamClient()
    insufficient_service, _ = service([candidate()], insufficient_llm)
    prepared = await insufficient_service.prepare("r-stream-no", AnswerRequest(query_text="q"))
    events = [event async for event in insufficient_service.stream_prepared(prepared)]
    assert [kind for kind, _ in events] == ["done"]
    assert events[0][1].status == GenerationStatus.INSUFFICIENT_EVIDENCE
    assert events[0][1].citations == []
    assert state == {"closed": True, "after_marker": False}
