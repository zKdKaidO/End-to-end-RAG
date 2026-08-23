from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.debug.schemas import (
    ChunkDetail,
    DebugRagRequest,
    DebugTrace,
    DocumentDetailView,
    DocumentPipelineView,
)
from app.debug.services import DebugRagService, DocumentObservabilityService
from app.generation.exceptions import (
    GenerationDependencyError,
    GenerationError,
    GenerationTimeoutError,
    GenerationValidationError,
)
from app.generation.profile import get_generation_profile
from app.generation.runtime import get_llm_client
from app.auth.access import DocumentAccessService, RESOURCE_NOT_FOUND
from app.auth.dependencies import require_admin
from app.auth.principal import Principal
from app.auth.scope import UserRetrievalScope
from app.models.chunk import Chunk
from app.models.document import Document
from sqlalchemy import select


router = APIRouter(prefix="/internal/debug", tags=["internal-debug"])


def require_debug_enabled():
    if not settings.DEBUG_UI_ENABLED or settings.APP_ENV.lower() not in {
        "development",
        "local",
        "test",
    }:
        raise HTTPException(status_code=404, detail="Debug endpoints are disabled")


def _generation_error(exc: GenerationError) -> HTTPException:
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


@router.get("/status", dependencies=[Depends(require_admin), Depends(require_debug_enabled)])
async def debug_status(_principal: Principal = Depends(require_admin)):
    profile = get_generation_profile()
    try:
        await get_llm_client().health(profile)
        provider = "available"
    except Exception:
        provider = "unavailable"
    return {"api": "available", "provider": provider, "model_id": profile.model_id}


@router.post(
    "/rag",
    response_model=DebugTrace,
    dependencies=[Depends(require_admin), Depends(require_debug_enabled)],
)
async def debug_rag(payload: DebugRagRequest, request: Request, db: Session = Depends(get_db), principal: Principal = Depends(require_admin)):
    try:
        if payload.document_ids:
            from uuid import UUID
            DocumentAccessService(db).require_all_accessible(principal.user_id, [UUID(value) for value in payload.document_ids])
        return await DebugRagService(db, access_scope=UserRetrievalScope(principal.user_id)).run(request.state.request_id, payload)
    except HTTPException:
        raise
    except GenerationError as exc:
        raise _generation_error(exc) from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"stage": "DEBUG_TRACE", "message": "Unable to build debug trace"},
        ) from exc


@router.get(
    "/chunks/{chunk_id}",
    response_model=ChunkDetail,
    dependencies=[Depends(require_admin), Depends(require_debug_enabled)],
)
def chunk_detail(chunk_id: str, db: Session = Depends(get_db), principal: Principal = Depends(require_admin)):
    try:
        from uuid import UUID
        chunk = db.scalar(select(Chunk).where(Chunk.id == UUID(chunk_id)))
        if chunk is None:
            raise KeyError(chunk_id)
        DocumentAccessService(db).require_accessible(principal.user_id, chunk.document_id)
        return DocumentObservabilityService(db).chunk(chunk_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid chunk UUID") from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Chunk not found") from exc


@router.get(
    "/documents",
    response_model=list[DocumentPipelineView],
    dependencies=[Depends(require_admin), Depends(require_debug_enabled)],
)
def documents(db: Session = Depends(get_db), principal: Principal = Depends(require_admin)):
    access = DocumentAccessService(db)
    ids = db.scalars(select(Document.id).where(access.predicate(principal.user_id, Document.id))).all()
    service = DocumentObservabilityService(db)
    return [service.detail(str(document_id)) for document_id in ids]


@router.get(
    "/documents/{document_id}",
    response_model=DocumentDetailView,
    dependencies=[Depends(require_admin), Depends(require_debug_enabled)],
)
def document_detail(document_id: str, db: Session = Depends(get_db), principal: Principal = Depends(require_admin)):
    try:
        from uuid import UUID
        DocumentAccessService(db).require_accessible(principal.user_id, UUID(document_id))
        return DocumentObservabilityService(db).detail(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid document UUID") from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
