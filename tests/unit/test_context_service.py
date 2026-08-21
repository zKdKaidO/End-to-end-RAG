from uuid import UUID

import pytest
from pydantic import ValidationError

from app.context.exceptions import ContextBuilderError, ContextValidationError, TokenCounterDependencyError
from app.context.schemas import ContextPackage, StopReason
from app.context.service import ContextBuilderService
from tests.context_doubles import CharacterTokenCounter, FailingTokenCounter


def candidate(number=1, rank=1, text="Điều 1. Nội dung"):
    return {
        "chunk_id": str(UUID(int=number)),
        "document_id": str(UUID(int=10)),
        "content_text": text,
        "metadata_json": {"title": "Văn bản thật"},
        "provenance_json": {"page_start": 1, "page_end": 1},
        "dense_score": 0.8,
        "dense_rank": rank,
        "lexical_score": None,
        "lexical_rank": None,
        "fusion_score": 0.02,
        "final_rank": rank,
    }


def service(counter=None):
    return ContextBuilderService(counter or CharacterTokenCounter())


def build(candidates, budget=10_000):
    return service().build(
        request_id="request-123",
        query_text="Doanh nghiệp được hưởng ưu đãi gì?",
        retrieved_candidates=candidates,
        context_budget_tokens=budget,
    )


def test_empty_retrieval_is_valid():
    package = build([])
    assert package == ContextPackage(
        request_id="request-123",
        query_text="Doanh nghiệp được hưởng ưu đãi gì?",
        context_text="",
        selected_evidence=[],
        context_token_count=0,
        context_budget_tokens=10_000,
        candidate_count=0,
        duplicate_count=0,
        selected_count=0,
        dropped_count=0,
        budget_exhausted=False,
        stop_reason=StopReason.NONE,
    )


def test_hierarchy_child_nullable_ir_signals_and_context_order_are_preserved():
    anchor = candidate(number=1, rank=1, text="Điều 1")
    anchor["legal_unit_id"] = str(UUID(int=100))
    hierarchy = {
        "chunk_id": str(UUID(int=2)),
        "document_id": str(UUID(int=10)),
        "content_text": "Khoản 1",
        "metadata_json": {"title": "Văn bản thật"},
        "provenance_json": {"page_start": 2, "page_end": 2},
        "dense_score": None,
        "dense_rank": None,
        "lexical_score": None,
        "lexical_rank": None,
        "fusion_score": None,
        "retrieval_final_rank": None,
        "final_rank": None,
        "context_candidate_order": 2,
        "candidate_origin": "HIERARCHY_CHILD",
        "legal_unit_id": str(UUID(int=101)),
        "hierarchy_relation": "DIRECT_CHILD",
        "hierarchy_depth": 1,
        "anchor_chunk_id": str(UUID(int=1)),
        "anchor_legal_unit_id": str(UUID(int=100)),
        "anchor_retrieval_final_rank": 1,
        "hierarchy_anchor_references": [{
            "anchor_chunk_id": str(UUID(int=1)),
            "anchor_legal_unit_id": str(UUID(int=100)),
            "anchor_retrieval_final_rank": 1,
        }],
    }
    package = build([anchor, hierarchy])
    assert [item.source_id for item in package.selected_evidence] == ["S1", "S2"]
    selected = package.selected_evidence[1]
    assert selected.retrieval_final_rank is None
    assert selected.context_candidate_order == 2
    assert selected.candidate_origin.value == "HIERARCHY_CHILD"
    assert selected.fusion_score is None
    assert selected.provenance_json == hierarchy["provenance_json"]


@pytest.mark.parametrize("budget", [0, -1, True, 1.5])
def test_invalid_budget_is_rejected(budget):
    with pytest.raises(ContextValidationError) as exc_info:
        build([], budget)
    assert exc_info.value.stage == "VALIDATE_INPUT"


def test_tokencounter_dependency_is_required_and_injected():
    with pytest.raises(ContextValidationError):
        ContextBuilderService(None)
    counter = CharacterTokenCounter()
    package = ContextBuilderService(counter).build(
        request_id="r", query_text="q", retrieved_candidates=[], context_budget_tokens=1
    )
    assert counter.calls == [""]
    assert package.context_token_count == 0


def test_missing_content_and_invalid_candidate_shape_are_rejected():
    missing = candidate()
    missing.pop("content_text")
    with pytest.raises(ContextValidationError):
        build([missing])
    with pytest.raises(ContextValidationError):
        build([candidate(text="   ")])


def test_invalid_uuid_and_out_of_order_ranks_are_rejected():
    invalid_uuid = candidate()
    invalid_uuid["chunk_id"] = "invalid"
    with pytest.raises(ContextValidationError):
        build([invalid_uuid])
    with pytest.raises(ContextValidationError, match="increasing context_candidate_order"):
        build([candidate(1, 2), candidate(2, 1)])


def test_duplicate_only_candidates_have_documented_drop_counts():
    items = [candidate(1, 1), candidate(2, 2, "  Điều 1.\nNội dung "), candidate(3, 3)]
    package = build(items)
    assert package.candidate_count == 3
    assert package.duplicate_count == 2
    assert package.selected_count == 1
    assert package.dropped_count == 2
    assert package.budget_exhausted is False
    assert package.stop_reason == StopReason.NONE


def test_machine_provenance_and_raw_ranking_signals_are_unchanged():
    original = candidate()
    package = build([original])
    selected = package.selected_evidence[0]
    assert selected.chunk_id == original["chunk_id"]
    assert selected.document_id == original["document_id"]
    assert selected.metadata_json == original["metadata_json"]
    assert selected.provenance_json == original["provenance_json"]
    assert selected.retrieval_final_rank == original["final_rank"]
    assert selected.dense_score == original["dense_score"]
    assert selected.fusion_score == original["fusion_score"]


def test_token_counter_failure_is_typed_dependency_error():
    with pytest.raises(TokenCounterDependencyError) as exc_info:
        ContextBuilderService(FailingTokenCounter()).build(
            request_id="r",
            query_text="q",
            retrieved_candidates=[candidate()],
            context_budget_tokens=100,
        )
    assert exc_info.value.stage == "TOKEN_COUNTING"


def test_schema_rejects_arbitrary_stop_reason():
    data = build([]).model_dump()
    data["stop_reason"] = "ARBITRARY"
    with pytest.raises(ValidationError):
        ContextPackage.model_validate(data)


def test_observability_contains_diagnostics_but_not_source_content(monkeypatch):
    class RecordingLogger:
        def __init__(self):
            self.events = []

        def info(self, event, **kwargs):
            self.events.append((event, kwargs))

    recording = RecordingLogger()
    monkeypatch.setattr("app.context.service.logger", recording)
    marker = "SENSITIVE_LEGAL_CONTENT_MARKER"
    package = build([candidate(text=marker)])
    completed = dict(recording.events)["context_build_completed"]
    required = {
        "request_id",
        "candidate_count",
        "duplicate_count",
        "selected_count",
        "dropped_count",
        "context_budget_tokens",
        "context_token_count",
        "budget_utilization",
        "budget_exhausted",
        "stop_reason",
        "context_build_ms",
        "tokenizer_provider",
        "tokenizer_id",
    }
    assert required <= completed.keys()
    serialized_events = repr(recording.events)
    assert marker not in serialized_events
    assert package.context_text not in serialized_events
