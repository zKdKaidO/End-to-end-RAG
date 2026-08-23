import asyncio
from contextlib import suppress
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.database import get_db
from app.generation.exceptions import (
    GenerationConfigurationError,
    GenerationDependencyError,
    GenerationError,
    GenerationTimeoutError,
    GenerationValidationError,
)
from app.generation.profile import get_generation_profile
from app.generation.runtime import get_llm_client
from app.generation.schemas import AnswerRequest, GenerationResult
from app.orchestration.answer_service import AnswerService
from app.retrieval.service import RetrievalService
from app.auth.access import DocumentAccessService
from app.auth.dependencies import require_authenticated_user
from app.auth.principal import Principal
from app.auth.scope import UserRetrievalScope
from app.security.rate_limits import SecurityControlUnavailable, generation_admission


router = APIRouter(tags=["answer"])
logger = get_logger(__name__)


class ClientDisconnected(Exception):
    pass


async def guarded_upstream(upstream, is_disconnected):
    """Cancel and close an upstream async generator when the client leaves."""
    try:
        while True:
            next_item = asyncio.create_task(anext(upstream))
            while not next_item.done():
                await asyncio.wait({next_item}, timeout=0.1)
                if await is_disconnected():
                    next_item.cancel()
                    with suppress(asyncio.CancelledError):
                        await next_item
                    raise ClientDisconnected
            try:
                yield next_item.result()
            except StopAsyncIteration:
                return
            if await is_disconnected():
                raise ClientDisconnected
    finally:
        await upstream.aclose()


def get_answer_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_authenticated_user),
) -> AnswerService:
    try:
        return AnswerService(RetrievalService(db, access_scope=UserRetrievalScope(principal.user_id)), get_llm_client(), get_generation_profile())
    except GenerationError as exc:
        raise _http_error(exc) from exc
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail={"stage": "VALIDATE_REQUEST", "error_code": "GENERATION_PROFILE_INVALID", "message": "Generation profile is invalid"},
        ) from exc


def _http_error(exc: GenerationError) -> HTTPException:
    if isinstance(exc, GenerationValidationError):
        status = 400
    elif isinstance(exc, GenerationTimeoutError):
        status = 504
    elif isinstance(exc, GenerationDependencyError):
        status = 503
    else:
        status = 500
    return HTTPException(
        status_code=status,
        detail={"stage": exc.stage, "error_code": exc.error_code, "message": exc.message},
    )


def _parse_request(payload: dict[str, Any]) -> AnswerRequest:
    try:
        return AnswerRequest.model_validate(payload)
    except ValidationError as exc:
        message = "; ".join(error["msg"] for error in exc.errors())
        raise GenerationValidationError("VALIDATE_REQUEST", "INVALID_REQUEST", message) from exc


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/answer", response_model=GenerationResult)
async def answer(
    request: Request,
    payload: dict[str, Any] = Body(...),
    service: AnswerService = Depends(get_answer_service),
    principal: Principal = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
    lease = None
    try:
        parsed = _parse_request(payload)
        if parsed.document_ids:
            DocumentAccessService(db).require_all_accessible(principal.user_id, [UUID(value) for value in parsed.document_ids])
        try:
            decision, lease = generation_admission.acquire(str(principal.user_id))
        except SecurityControlUnavailable as exc:
            raise HTTPException(503, detail={"stage": "ADMISSION", "error_code": "SECURITY_CONTROL_UNAVAILABLE", "message": "Generation is temporarily unavailable."}) from exc
        if not decision.allowed:
            raise HTTPException(
                429,
                detail={"stage": "ADMISSION", "error_code": decision.reason, "message": "Generation capacity is temporarily unavailable."},
                headers={"Retry-After": str(decision.retry_after_seconds)},
            )
        return await service.answer(request.state.request_id, parsed)
    except GenerationError as exc:
        logger.warning("answer_request_failed", request_id=request.state.request_id, stage=exc.stage, error_code=exc.error_code)
        raise _http_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("answer_unexpected_error", request_id=request.state.request_id, stage="FINALIZE")
        raise HTTPException(
            status_code=500,
            detail={"stage": "FINALIZE", "error_code": "INTERNAL_ERROR", "message": "Unexpected generation error"},
        ) from exc
    finally:
        generation_admission.release(lease)


@router.post("/answer/stream")
async def answer_stream(
    request: Request,
    payload: dict[str, Any] = Body(...),
    service: AnswerService = Depends(get_answer_service),
    principal: Principal = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
    lease = None
    try:
        parsed = _parse_request(payload)
        if parsed.document_ids:
            DocumentAccessService(db).require_all_accessible(principal.user_id, [UUID(value) for value in parsed.document_ids])
        try:
            decision, lease = generation_admission.acquire(str(principal.user_id))
        except SecurityControlUnavailable as exc:
            raise HTTPException(503, detail={"stage": "ADMISSION", "error_code": "SECURITY_CONTROL_UNAVAILABLE", "message": "Generation is temporarily unavailable."}) from exc
        if not decision.allowed:
            raise HTTPException(
                429,
                detail={"stage": "ADMISSION", "error_code": decision.reason, "message": "Generation capacity is temporarily unavailable."},
                headers={"Retry-After": str(decision.retry_after_seconds)},
            )
        prepared = await service.prepare(request.state.request_id, parsed)
        await service.check_provider(prepared)
    except GenerationError as exc:
        generation_admission.release(lease)
        raise _http_error(exc) from exc
    except HTTPException:
        generation_admission.release(lease)
        raise
    except Exception as exc:
        generation_admission.release(lease)
        logger.exception("answer_stream_preparation_failed", request_id=request.state.request_id)
        raise HTTPException(
            status_code=500,
            detail={"stage": "FINALIZE", "error_code": "INTERNAL_ERROR", "message": "Unexpected generation error"},
        ) from exc

    async def events():
        yield _sse(
            "start",
            {
                "request_id": prepared.request_id,
                "model_id": service.profile.model_id,
                "prompt_version": service.profile.prompt_version,
            },
        )
        upstream = service.stream_prepared(prepared)
        try:
            async for event, value in guarded_upstream(upstream, request.is_disconnected):
                if event == "delta":
                    yield _sse("delta", {"text": value})
                else:
                    yield _sse("done", value.model_dump(mode="json"))
        except ClientDisconnected:
            logger.info("answer_stream_disconnected", request_id=prepared.request_id, stage="CLIENT_DISCONNECTED")
            return
        except asyncio.CancelledError:
            await upstream.aclose()
            logger.info("answer_stream_cancelled", request_id=prepared.request_id, stage="CLIENT_DISCONNECTED")
            raise
        except GenerationError as exc:
            yield _sse(
                "error",
                {
                    "request_id": prepared.request_id,
                    "stage": exc.stage,
                    "error_type": exc.error_code,
                    "safe_message": exc.message,
                },
            )
        finally:
            await upstream.aclose()
            generation_admission.release(lease)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
