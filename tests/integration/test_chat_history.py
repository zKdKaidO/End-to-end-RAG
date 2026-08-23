import uuid
import asyncio
import hashlib
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.api.routes.answer import get_answer_service
from app.chat.schemas import ChatTurnRequest
from app.chat.service import ChatError, ChatHistoryService, content_sha256
from app.context.schemas import ContextPackage, SelectedEvidence, StopReason
from app.db.database import SessionLocal
from app.generation.schemas import (
    AnswerabilityStatus,
    AnswerabilityValidation,
    Citation,
    CitationValidation,
    GenerationResult,
    GenerationStatus,
    Usage,
)
from app.generation.exceptions import GenerationDependencyError
from app.main import app
from app.models.chat import ChatMessage, ChatSession, ChatTurn, DeliveryState, MessageCitationSnapshot, TurnState, utcnow
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus


def evidence() -> SelectedEvidence:
    return SelectedEvidence(
        source_id="S1", chunk_id=str(uuid.uuid4()), document_id=str(uuid.uuid4()), legal_unit_id=str(uuid.uuid4()),
        content_text="Điều 1 quy định nội dung kiểm tra.", metadata_json={"article": "1", "title": "Luật thử"},
        provenance_json={"page_start": 2, "page_end": 2}, retrieval_final_rank=1, context_candidate_order=1,
        dense_score=.9, dense_rank=1, lexical_score=.5, lexical_rank=1, fusion_score=.03, token_count=10,
    )


def package(item: SelectedEvidence | None = None) -> ContextPackage:
    selected = [item or evidence()]
    return ContextPackage(
        request_id="chat-test", query_text="Quy định gì?", context_text="context", selected_evidence=selected,
        context_token_count=10, context_budget_tokens=100, candidate_count=1, duplicate_count=0,
        selected_count=1, dropped_count=0, budget_exhausted=False, stop_reason=StopReason.NONE,
    )


def completed_result(item: SelectedEvidence | None = None) -> GenerationResult:
    item = item or evidence()
    return GenerationResult(
        request_id="chat-test", status=GenerationStatus.COMPLETED, answer_text="Nội dung [S1]",
        citations=[Citation(source_id="S1", chunk_id=item.chunk_id, document_id=item.document_id, metadata_json=item.metadata_json, provenance_json=item.provenance_json)],
        invalid_citations=[], citation_validation=CitationValidation.PASS, model_id="qwen3.5:9b",
        prompt_version="legal-rag-v2", finish_reason="stop", usage=Usage(input_tokens=11, output_tokens=4, total_tokens=15),
        answerability_status=AnswerabilityStatus.ANSWERABLE, answerability_validation=AnswerabilityValidation.PASS,
    )


@pytest.fixture
def db():
    session = SessionLocal()
    existing_ids = set(session.scalars(select(ChatSession.id)).all())
    yield session
    session.rollback()
    created_ids = set(session.scalars(select(ChatSession.id)).all()) - existing_ids
    if created_ids:
        session.execute(delete(ChatSession).where(ChatSession.id.in_(created_ids)))
        session.commit()
    session.close()


def request(client_id=None, query="Quy định gì?"):
    return ChatTurnRequest(client_turn_id=client_id or uuid.uuid4(), query=query)


def test_schema_constraints_idempotency_and_history_cascade(db):
    service = ChatHistoryService(db)
    chat = service.create_session()
    client_id = uuid.uuid4()
    handle = service.begin_turn(chat.id, request(client_id))
    with pytest.raises(ChatError) as progress:
        service.begin_turn(chat.id, request(client_id))
    assert progress.value.code == "TURN_IN_PROGRESS"
    with pytest.raises(ChatError) as conflict:
        service.begin_turn(chat.id, request(client_id, "Khác"))
    assert conflict.value.code == "IDEMPOTENCY_KEY_CONFLICT"
    with pytest.raises(ChatError) as active:
        service.begin_turn(chat.id, request())
    assert active.value.code == "SESSION_TURN_IN_PROGRESS"

    item = evidence()
    service.finalize_turn(handle, completed_result(item), package(item), "request-1", {"generation_ms": 12.6})
    replay = service.begin_turn(chat.id, request(client_id))
    assert replay.replayed is True
    assert db.scalar(select(func.count(ChatTurn.id)).where(ChatTurn.session_id == chat.id)) == 1
    assert db.scalar(
        select(func.count(MessageCitationSnapshot.id)).where(MessageCitationSnapshot.message_id == handle.assistant_message_id)
    ) == 1
    assistant = db.get(ChatMessage, handle.assistant_message_id)
    assert assistant.finalized_at and assistant.generation_latency_ms == 13
    assert assistant.context_fingerprint and assistant.prompt_hash and assistant.index_version == "block3-v1"
    assert assistant.citation_snapshots[0].chunk_content_sha256 == content_sha256(item.content_text)

    service.delete_session(chat.id)
    assert db.scalar(select(func.count(ChatMessage.id)).where(ChatMessage.session_id == chat.id)) == 0
    assert db.scalar(
        select(func.count(MessageCitationSnapshot.id)).where(MessageCitationSnapshot.message_id == handle.assistant_message_id)
    ) == 0


def test_database_partial_unique_active_turn_constraint(db):
    chat = ChatHistoryService(db).create_session()
    first = ChatTurn(session_id=chat.id, client_turn_id=uuid.uuid4(), request_hash="a" * 64, state="STREAMING", created_at=utcnow(), started_at=utcnow())
    db.add(first); db.commit()
    second = ChatTurn(session_id=chat.id, client_turn_id=uuid.uuid4(), request_hash="b" * 64, state="PENDING", created_at=utcnow())
    db.add(second)
    with pytest.raises(IntegrityError) as caught:
        db.commit()
    db.rollback()
    assert caught.value.orig.diag.constraint_name == "uq_chat_turn_one_active_per_session"


def test_stale_orphan_recovery_unlocks_session_and_fresh_stream_is_preserved(db, monkeypatch):
    service = ChatHistoryService(db)
    chat = service.create_session()
    stale = service.begin_turn(chat.id, request())
    turn = db.get(ChatTurn, stale.turn_id)
    turn.started_at = utcnow() - timedelta(seconds=601)
    db.commit()
    service.get_session(chat.id)
    db.expire_all()
    assert db.get(ChatTurn, stale.turn_id).state == TurnState.FAILED.value
    assert db.get(ChatTurn, stale.turn_id).failure_code == "ORPHANED_STREAM_TIMEOUT"
    assert db.get(ChatMessage, stale.assistant_message_id).delivery_state == DeliveryState.FAILED.value
    new_handle = service.begin_turn(chat.id, request())
    service.get_session(chat.id)
    assert db.get(ChatTurn, new_handle.turn_id).state == TurnState.STREAMING.value


def test_insufficient_completion_has_zero_snapshots_and_atomic_failure_never_completes(db, monkeypatch):
    service = ChatHistoryService(db)
    chat = service.create_session()
    handle = service.begin_turn(chat.id, request())
    insufficient = completed_result()
    insufficient.status = GenerationStatus.INSUFFICIENT_EVIDENCE
    insufficient.answer_text = "Không đủ bằng chứng."
    insufficient.answerability_status = AnswerabilityStatus.INSUFFICIENT_EVIDENCE
    insufficient.citations = []
    service.finalize_turn(handle, insufficient, package(), "r")
    assert db.scalar(
        select(func.count(MessageCitationSnapshot.id)).where(MessageCitationSnapshot.message_id == handle.assistant_message_id)
    ) == 0

    second = service.begin_turn(chat.id, request())
    original = service._snapshot
    def broken(*args, **kwargs):
        value = original(*args, **kwargs)
        value.evidence_text = None
        return value
    monkeypatch.setattr(service, "_snapshot", broken)
    item = evidence()
    with pytest.raises(IntegrityError):
        service.finalize_turn(second, completed_result(item), package(item), "r")
    db.expire_all()
    assert db.get(ChatTurn, second.turn_id).state == TurnState.STREAMING.value
    assert db.get(ChatMessage, second.assistant_message_id).delivery_state == DeliveryState.STREAMING.value
    service.mark_terminal(second, TurnState.FAILED, "HISTORY_FINALIZATION_FAILED", "safe")
    assert db.get(ChatTurn, second.turn_id).state == TurnState.FAILED.value


class FakePersistentAnswerService:
    def __init__(self, item):
        self.item = item
        self.calls = 0
        self.profile = SimpleNamespace(model_id="qwen3.5:9b", prompt_version="legal-rag-v2")

    async def prepare(self, request_id, request):
        return SimpleNamespace(request_id=request_id, package=package(self.item), timings={"generation_ms": 2.0})

    async def check_provider(self, prepared):
        return None

    async def stream_prepared(self, prepared):
        self.calls += 1
        yield "delta", "Nội dung "
        yield "done", completed_result(self.item)


def test_product_stream_persists_replays_and_history_uses_snapshot(db):
    item = evidence()
    fake = FakePersistentAnswerService(item)
    app.dependency_overrides[get_answer_service] = lambda: fake
    client = TestClient(app)
    try:
        chat = client.post("/api/v1/chat/sessions", json={}).json()
        client_id = str(uuid.uuid4())
        url = f"/api/v1/chat/sessions/{chat['id']}/turns/stream"
        payload = {"client_turn_id": client_id, "query": "Quy định gì?", "document_ids": None}
        first = client.post(url, json=payload)
        assert first.status_code == 200 and "event: done" in first.text
        history = client.get(f"/api/v1/chat/sessions/{chat['id']}/messages").json()["data"]
        assistant = history[1]
        assert assistant["delivery_state"] == "COMPLETED"
        assert assistant["citations"][0]["evidence_text"] == item.content_text
        assert assistant["citations"][0]["availability"] == "SOURCE_UNAVAILABLE"

        replay = client.post(url, json=payload)
        assert '"replayed": true' in replay.text
        assert fake.calls == 1
        assert db.scalar(
            select(func.count(MessageCitationSnapshot.id)).where(MessageCitationSnapshot.message_id == uuid.UUID(assistant["id"]))
        ) == 1
    finally:
        app.dependency_overrides.clear()


def test_message_keyset_pagination_and_no_message_mutation_routes(db):
    service = ChatHistoryService(db)
    chat = service.create_session()
    for index in range(4):
        handle = service.begin_turn(chat.id, request(query=f"Q{index}"))
        item = evidence()
        service.finalize_turn(handle, completed_result(item), package(item), f"r{index}")
    rows, before, _ = service.load_messages(chat.id, 3, None)
    assert [row.sequence_no for row in rows] == [6, 7, 8] and before == 6
    older, before2, _ = service.load_messages(chat.id, 3, before)
    assert [row.sequence_no for row in older] == [3, 4, 5] and before2 == 3

    client = TestClient(app)
    assert client.patch(f"/api/v1/chat/messages/{rows[-1].id}", json={"content": "edit"}).status_code == 404
    assert client.delete(f"/api/v1/chat/messages/{rows[-1].id}").status_code == 404


def test_real_postgres_concurrent_begin_turn_races_create_one_active_row(db):
    chat_id = ChatHistoryService(db).create_session().id
    client_id = uuid.uuid4()

    def begin(turn_id, query):
        local = SessionLocal()
        try:
            handle = ChatHistoryService(local).begin_turn(chat_id, request(turn_id, query))
            return ("OK", str(handle.turn_id), handle.replayed)
        except ChatError as exc:
            return (exc.code, exc.details.get("turn_id"), False)
        finally:
            local.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        identical = list(pool.map(lambda _: begin(client_id, "Cùng câu hỏi"), range(2)))
    assert sorted(item[0] for item in identical) == ["OK", "TURN_IN_PROGRESS"]
    assert db.scalar(select(func.count(ChatTurn.id)).where(ChatTurn.session_id == chat_id)) == 1

    active = db.scalar(select(ChatTurn).where(ChatTurn.session_id == chat_id))
    active.state = TurnState.FAILED.value; active.completed_at = utcnow(); active.failure_code = "TEST"; db.commit()
    conflict_id = uuid.uuid4()
    with ThreadPoolExecutor(max_workers=2) as pool:
        conflict = list(pool.map(lambda query: begin(conflict_id, query), ["Một", "Hai"]))
    assert sorted(item[0] for item in conflict) == ["IDEMPOTENCY_KEY_CONFLICT", "OK"]

    current = db.scalar(select(ChatTurn).where(ChatTurn.session_id == chat_id, ChatTurn.state.in_(("PENDING", "STREAMING"))))
    current.state = TurnState.FAILED.value; current.completed_at = utcnow(); current.failure_code = "TEST"; db.commit()
    with ThreadPoolExecutor(max_workers=2) as pool:
        different = list(pool.map(lambda _: begin(uuid.uuid4(), "Q"), range(2)))
    assert sorted(item[0] for item in different) == ["OK", "SESSION_TURN_IN_PROGRESS"]
    assert db.scalar(select(func.count(ChatTurn.id)).where(ChatTurn.session_id == chat_id, ChatTurn.state.in_(("PENDING", "STREAMING")))) == 1


def test_snapshot_survives_document_delete_and_resolves_uuid_drift(db):
    sha = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    document = Document(
        filename="history-fixture.pdf", mime_type="application/pdf", file_size=10, sha256=sha,
        status=DocumentStatus.COMPLETED, created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(document); db.flush()
    chunk = Chunk(
        document_id=document.id, legal_unit_id=None, chunk_index=0, content_text="Bằng chứng lịch sử bất biến.",
        embedding_text="passage: Bằng chứng lịch sử bất biến.", page_start=4, page_end=4,
        metadata_json={"article": "9"}, provenance_json={"page_start": 4}, created_at=utcnow(),
    )
    db.add(chunk); db.commit()
    original_chunk_id = chunk.id
    item = evidence().model_copy(update={
        "document_id": str(document.id), "chunk_id": str(chunk.id), "legal_unit_id": None,
        "content_text": chunk.content_text, "metadata_json": chunk.metadata_json, "provenance_json": chunk.provenance_json,
    })
    service = ChatHistoryService(db)
    chat = service.create_session()
    handle = service.begin_turn(chat.id, request())
    service.finalize_turn(handle, completed_result(item), package(item), "lifecycle")
    snapshot_id = db.scalar(select(MessageCitationSnapshot.id).where(MessageCitationSnapshot.message_id == handle.assistant_message_id))

    document.sha256 = hashlib.sha256(b"updated-document").hexdigest(); db.commit()
    rows, _, availability = service.load_messages(chat.id, 50, None)
    assert availability[snapshot_id]["availability"] == "SOURCE_UPDATED"
    document.sha256 = sha; db.commit()

    db.delete(document); db.commit()
    assert db.get(Chunk, original_chunk_id) is None
    rows, _, availability = service.load_messages(chat.id, 50, None)
    snapshot = next(message for message in rows if message.role == "ASSISTANT").citation_snapshots[0]
    assert snapshot.evidence_text == "Bằng chứng lịch sử bất biến."
    assert availability[snapshot_id]["availability"] == "SOURCE_UNAVAILABLE"

    replacement = Document(
        filename="history-fixture-reprocessed.pdf", mime_type="application/pdf", file_size=10, sha256=sha,
        status=DocumentStatus.COMPLETED, created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(replacement); db.flush()
    replacement_chunk = Chunk(
        document_id=replacement.id, legal_unit_id=None, chunk_index=0, content_text=snapshot.evidence_text,
        embedding_text=f"passage: {snapshot.evidence_text}", page_start=4, page_end=4,
        metadata_json={"article": "9"}, provenance_json={"page_start": 4}, created_at=utcnow(),
    )
    db.add(replacement_chunk); db.commit()
    rows, _, availability = service.load_messages(chat.id, 50, None)
    same_snapshot = next(message for message in rows if message.role == "ASSISTANT").citation_snapshots[0]
    assert same_snapshot.original_chunk_id == original_chunk_id
    assert same_snapshot.evidence_text == snapshot.evidence_text
    assert availability[snapshot_id]["availability"] == "CURRENT_EQUIVALENT"
    assert availability[snapshot_id]["current_chunk_id"] == replacement_chunk.id
    db.delete(replacement); db.commit()


def test_concurrent_product_stream_invokes_provider_once(db):
    item = evidence()
    fake = FakePersistentAnswerService(item)
    original_stream = fake.stream_prepared

    async def delayed(prepared):
        await asyncio.sleep(.15)
        async for value in original_stream(prepared):
            yield value
    fake.stream_prepared = delayed
    app.dependency_overrides[get_answer_service] = lambda: fake
    chat_id = str(ChatHistoryService(db).create_session().id)
    client_id = str(uuid.uuid4())
    payload = {"client_turn_id": client_id, "query": "Một câu hỏi", "document_ids": None}

    def post():
        with TestClient(app) as local:
            response = local.post(f"/api/v1/chat/sessions/{chat_id}/turns/stream", json=payload)
            return response.status_code, response.text
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: post(), range(2)))
        assert fake.calls == 1
        assert any(status == 200 and "event: done" in body for status, body in responses)
        assert all(status in (200, 409) for status, _ in responses)
        assert db.scalar(select(func.count(ChatTurn.id)).where(ChatTurn.session_id == uuid.UUID(chat_id))) == 1
    finally:
        app.dependency_overrides.clear()


def test_product_stream_finalization_failure_emits_error_never_done(db, monkeypatch):
    item = evidence()
    fake = FakePersistentAnswerService(item)
    app.dependency_overrides[get_answer_service] = lambda: fake
    chat_id = str(ChatHistoryService(db).create_session().id)
    original = ChatHistoryService.finalize_turn
    monkeypatch.setattr(ChatHistoryService, "finalize_turn", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("injected")))
    try:
        response = TestClient(app).post(
            f"/api/v1/chat/sessions/{chat_id}/turns/stream",
            json={"client_turn_id": str(uuid.uuid4()), "query": "Q", "document_ids": None},
        )
        assert response.status_code == 200
        assert "event: error" in response.text and "event: done" not in response.text
        turn = db.scalar(select(ChatTurn).where(ChatTurn.session_id == uuid.UUID(chat_id)))
        db.expire_all()
        assert db.get(ChatTurn, turn.id).state == TurnState.FAILED.value
        assert db.get(ChatTurn, turn.id).failure_code == "HISTORY_FINALIZATION_FAILED"
        assert db.scalar(
            select(func.count(MessageCitationSnapshot.id))
            .join(ChatMessage, ChatMessage.id == MessageCitationSnapshot.message_id)
            .where(ChatMessage.session_id == uuid.UUID(chat_id))
        ) == 0
    finally:
        monkeypatch.setattr(ChatHistoryService, "finalize_turn", original)
        app.dependency_overrides.clear()


def test_product_stream_provider_failure_is_persisted_and_never_emits_done(db):
    item = evidence()
    fake = FakePersistentAnswerService(item)

    async def unavailable(_prepared):
        raise GenerationDependencyError("LLM_REQUEST", "PROVIDER_UNAVAILABLE", "Provider unavailable.")

    fake.check_provider = unavailable
    app.dependency_overrides[get_answer_service] = lambda: fake
    chat_id = str(ChatHistoryService(db).create_session().id)
    try:
        response = TestClient(app).post(
            f"/api/v1/chat/sessions/{chat_id}/turns/stream",
            json={"client_turn_id": str(uuid.uuid4()), "query": "Q", "document_ids": None},
        )
        assert response.status_code == 200
        assert "event: error" in response.text and "event: done" not in response.text
        assert "PROVIDER_UNAVAILABLE" in response.text
        db.expire_all()
        turn = db.scalar(select(ChatTurn).where(ChatTurn.session_id == uuid.UUID(chat_id)))
        assert turn.state == TurnState.FAILED.value
        assert turn.failure_code == "PROVIDER_UNAVAILABLE"
        assert fake.calls == 0
        assert db.scalar(
            select(func.count(MessageCitationSnapshot.id))
            .join(ChatMessage, ChatMessage.id == MessageCitationSnapshot.message_id)
            .where(ChatMessage.session_id == uuid.UUID(chat_id))
        ) == 0
    finally:
        app.dependency_overrides.clear()


def test_session_api_rename_delete_busy_and_keyset_list(db):
    client = TestClient(app)
    first = client.post("/api/v1/chat/sessions", json={}).json()
    second = client.post("/api/v1/chat/sessions", json={"title": "Second"}).json()
    renamed = client.patch(f"/api/v1/chat/sessions/{first['id']}", json={"title": "  Renamed   title "})
    assert renamed.status_code == 200 and renamed.json()["title"] == "Renamed title"
    service = ChatHistoryService(db)
    service.begin_turn(uuid.UUID(first["id"]), request())
    busy = client.delete(f"/api/v1/chat/sessions/{first['id']}")
    assert busy.status_code == 409 and busy.json()["detail"]["error_code"] == "SESSION_BUSY"
    page = client.get("/api/v1/chat/sessions?limit=1").json()
    assert len(page["data"]) == 1 and page["next_cursor"]
    next_page = client.get(f"/api/v1/chat/sessions?limit=1&cursor={page['next_cursor']}")
    assert next_page.status_code == 200 and len(next_page.json()["data"]) == 1
    assert client.delete(f"/api/v1/chat/sessions/{second['id']}").status_code == 204
