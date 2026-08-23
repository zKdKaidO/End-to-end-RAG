import asyncio
import json
from contextlib import suppress
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.routes.answer import ClientDisconnected, guarded_upstream
from app.chat.schemas import (
    ChatMessagePage,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionList,
    ChatSessionPatch,
    ChatSessionSummary,
    ChatTurnRequest,
    CitationSnapshotResponse,
)
from app.chat.service import ChatError, ChatHistoryService, INTERRUPTED_MESSAGE
from app.core.config import settings
from app.core.logging import get_logger
from app.db.database import get_db
from app.generation.exceptions import GenerationError
from app.generation.schemas import AnswerRequest
from app.models.chat import TurnState
from app.orchestration.answer_service import AnswerService
from app.api.routes.answer import get_answer_service
from app.auth.access import DocumentAccessService
from app.auth.dependencies import require_authenticated_user
from app.auth.principal import Principal
from app.security.rate_limits import SecurityControlUnavailable, generation_admission


router = APIRouter(prefix="/api/v1/chat", tags=["chat"])
logger = get_logger(__name__)


def history_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_authenticated_user),
) -> ChatHistoryService:
    return ChatHistoryService(db, principal.user_id)


def chat_http_error(exc: ChatError) -> HTTPException:
    return HTTPException(exc.status_code, detail={"error_code": exc.code, "message": exc.message, **exc.details})


def session_response(item, message_count: int = 0, preview: str | None = None) -> ChatSessionSummary:
    return ChatSessionSummary(
        id=item.id,
        title=item.title,
        created_at=item.created_at,
        updated_at=item.updated_at,
        last_message_at=item.last_message_at,
        message_count=message_count,
        last_message_preview=preview,
    )


@router.post("/sessions", response_model=ChatSessionSummary, status_code=201)
def create_session(payload: ChatSessionCreate | None = Body(default=None), service: ChatHistoryService = Depends(history_service)):
    try:
        return session_response(service.create_session(payload.title if payload else None))
    except ChatError as exc:
        raise chat_http_error(exc) from exc


@router.get("/sessions", response_model=ChatSessionList)
def list_sessions(
    limit: int = Query(default=settings.CHAT_SESSION_PAGE_SIZE_DEFAULT, ge=1, le=settings.CHAT_SESSION_PAGE_SIZE_MAX),
    cursor: str | None = None,
    service: ChatHistoryService = Depends(history_service),
):
    try:
        data, next_cursor = service.list_sessions(limit, cursor)
        return {"data": data, "next_cursor": next_cursor}
    except ChatError as exc:
        raise chat_http_error(exc) from exc


@router.get("/sessions/{session_id}", response_model=ChatSessionSummary)
def get_session(session_id: UUID, service: ChatHistoryService = Depends(history_service)):
    try:
        return session_response(service.get_session(session_id))
    except ChatError as exc:
        raise chat_http_error(exc) from exc


@router.patch("/sessions/{session_id}", response_model=ChatSessionSummary)
def rename_session(session_id: UUID, payload: ChatSessionPatch, service: ChatHistoryService = Depends(history_service)):
    try:
        return session_response(service.rename_session(session_id, payload.title))
    except ChatError as exc:
        raise chat_http_error(exc) from exc


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: UUID, service: ChatHistoryService = Depends(history_service)):
    try:
        service.delete_session(session_id)
        return Response(status_code=204)
    except ChatError as exc:
        raise chat_http_error(exc) from exc


@router.get("/sessions/{session_id}/messages", response_model=ChatMessagePage)
def get_messages(
    session_id: UUID,
    before_sequence: int | None = Query(default=None, gt=0),
    limit: int = Query(default=settings.CHAT_MESSAGE_PAGE_SIZE_DEFAULT, ge=1, le=settings.CHAT_MESSAGE_PAGE_SIZE_MAX),
    service: ChatHistoryService = Depends(history_service),
):
    try:
        rows, next_before, availability = service.load_messages(session_id, limit, before_sequence)
        data = []
        for message in rows:
            turn = message.turn
            citations = []
            for item in message.citation_snapshots:
                current = availability.get(item.id, {"availability": "SOURCE_UNAVAILABLE"})
                citations.append(CitationSnapshotResponse(
                    id=item.id,
                    citation_label=item.citation_label,
                    citation_order=item.citation_order,
                    original_document_id=item.original_document_id,
                    original_chunk_id=item.original_chunk_id,
                    original_legal_unit_id=item.original_legal_unit_id,
                    document_title=item.document_title,
                    document_filename=item.document_filename,
                    document_sha256=item.document_sha256,
                    chunk_content_sha256=item.chunk_content_sha256,
                    page_start=item.page_start,
                    page_end=item.page_end,
                    article=item.article,
                    clause=item.clause,
                    point=item.point,
                    evidence_text=item.evidence_text,
                    metadata_json=item.metadata_json,
                    provenance_json=item.provenance_json,
                    snapshot_version=item.snapshot_version,
                    created_at=item.created_at,
                    **current,
                ))
            data.append(ChatMessageResponse(
                id=message.id,
                session_id=message.session_id,
                turn_id=message.turn_id,
                role=message.role,
                sequence_no=message.sequence_no,
                content=message.content,
                delivery_state=message.delivery_state,
                answer_status=message.answer_status,
                model_id=message.model_id,
                prompt_version=message.prompt_version,
                created_at=message.created_at,
                finalized_at=message.finalized_at,
                failure_code=turn.failure_code,
                failure_detail_safe=turn.failure_detail_safe,
                citations=citations,
            ))
        return {"data": data, "next_before_sequence": next_before}
    except ChatError as exc:
        raise chat_http_error(exc) from exc


def sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/sessions/{session_id}/turns/stream")
async def stream_turn(
    session_id: UUID,
    request: Request,
    payload: dict[str, Any] = Body(...),
    history: ChatHistoryService = Depends(history_service),
    answer_service: AnswerService = Depends(get_answer_service),
    principal: Principal = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
    try:
        turn_request = ChatTurnRequest.model_validate(payload)
        if turn_request.document_ids:
            DocumentAccessService(db).require_all_accessible(principal.user_id, turn_request.document_ids)
        handle = history.begin_turn(session_id, turn_request)
    except ValidationError as exc:
        raise HTTPException(400, detail={"error_code": "INVALID_REQUEST", "message": "; ".join(item["msg"] for item in exc.errors())}) from exc
    except ChatError as exc:
        raise chat_http_error(exc) from exc

    async def replay_events():
        result = history.replay_payload(handle)
        yield sse("start", {
            "request_id": result["request_id"], "turn_id": str(handle.turn_id),
            "user_message_id": str(handle.user_message_id), "assistant_message_id": str(handle.assistant_message_id),
            "model_id": result["model_id"], "prompt_version": result["prompt_version"], "replayed": True,
        })
        if result["answer_text"]:
            yield sse("delta", {"text": result["answer_text"]})
        yield sse("done", result)

    if handle.replayed:
        return StreamingResponse(replay_events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    try:
        decision, admission_lease = generation_admission.acquire(str(principal.user_id))
    except SecurityControlUnavailable as exc:
        history.mark_terminal(handle, TurnState.FAILED, "SECURITY_CONTROL_UNAVAILABLE", "Generation is temporarily unavailable.")
        raise HTTPException(503, detail={"error_code": "SECURITY_CONTROL_UNAVAILABLE", "message": "Generation is temporarily unavailable."}) from exc
    if not decision.allowed:
        history.mark_terminal(handle, TurnState.FAILED, decision.reason or "GENERATION_ADMISSION_REJECTED", "Generation capacity is temporarily unavailable.")
        raise HTTPException(
            429,
            detail={"error_code": decision.reason, "message": "Generation capacity is temporarily unavailable."},
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )

    async def events():
        visible: list[str] = []
        prepared = None
        upstream = None
        yield sse("start", {
            "request_id": request.state.request_id,
            "turn_id": str(handle.turn_id),
            "user_message_id": str(handle.user_message_id),
            "assistant_message_id": str(handle.assistant_message_id),
            "model_id": answer_service.profile.model_id,
            "prompt_version": answer_service.profile.prompt_version,
            "replayed": False,
        })
        try:
            prepared = await answer_service.prepare(
                request.state.request_id,
                AnswerRequest(query_text=turn_request.query, document_ids=[str(value) for value in turn_request.document_ids] if turn_request.document_ids else None),
            )
            await answer_service.check_provider(prepared)
            upstream = answer_service.stream_prepared(prepared)
            async for event, value in guarded_upstream(upstream, request.is_disconnected):
                if event == "delta":
                    visible.append(value)
                    yield sse("delta", {"text": value})
                else:
                    try:
                        history.finalize_turn(handle, value, prepared.package, request.state.request_id, prepared.timings)
                    except Exception:
                        logger.exception("chat_history_finalization_failed", request_id=request.state.request_id, turn_id=str(handle.turn_id))
                        history.mark_terminal(handle, TurnState.FAILED, "HISTORY_FINALIZATION_FAILED", "The answer could not be saved safely.", "".join(visible))
                        yield sse("error", {"request_id": request.state.request_id, "stage": "HISTORY_FINALIZATION", "error_type": "HISTORY_FINALIZATION_FAILED", "safe_message": "The answer could not be saved safely."})
                        return
                    yield sse("done", value.model_dump(mode="json"))
        except ClientDisconnected:
            history.mark_terminal(handle, TurnState.CANCELLED, "CLIENT_CANCELLED", "Generation was cancelled.", "".join(visible))
            return
        except asyncio.CancelledError:
            if upstream is not None:
                with suppress(Exception):
                    await upstream.aclose()
            history.mark_terminal(handle, TurnState.CANCELLED, "CLIENT_CANCELLED", "Generation was cancelled.", "".join(visible))
            raise
        except GenerationError as exc:
            history.mark_terminal(handle, TurnState.FAILED, exc.error_code, exc.message, "".join(visible))
            yield sse("error", {"request_id": request.state.request_id, "stage": exc.stage, "error_type": exc.error_code, "safe_message": exc.message})
        except Exception:
            logger.exception("chat_turn_failed", request_id=request.state.request_id, turn_id=str(handle.turn_id))
            history.mark_terminal(handle, TurnState.FAILED, "INTERNAL_ERROR", "Generation failed safely.", "".join(visible))
            yield sse("error", {"request_id": request.state.request_id, "stage": "CHAT_STREAM", "error_type": "INTERNAL_ERROR", "safe_message": "Generation failed safely."})
        finally:
            if upstream is not None:
                with suppress(Exception):
                    await upstream.aclose()
            generation_admission.release(admission_lease)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
