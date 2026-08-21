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


@router.get("/status", dependencies=[Depends(require_debug_enabled)])
async def debug_status():
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
    dependencies=[Depends(require_debug_enabled)],
)
async def debug_rag(payload: DebugRagRequest, request: Request, db: Session = Depends(get_db)):
    try:
        return await DebugRagService(db).run(request.state.request_id, payload)
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
    dependencies=[Depends(require_debug_enabled)],
)
def chunk_detail(chunk_id: str, db: Session = Depends(get_db)):
    try:
        return DocumentObservabilityService(db).chunk(chunk_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid chunk UUID") from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Chunk not found") from exc


@router.get(
    "/documents",
    response_model=list[DocumentPipelineView],
    dependencies=[Depends(require_debug_enabled)],
)
def documents(db: Session = Depends(get_db)):
    return DocumentObservabilityService(db).list()


@router.get(
    "/documents/{document_id}",
    response_model=DocumentDetailView,
    dependencies=[Depends(require_debug_enabled)],
)
def document_detail(document_id: str, db: Session = Depends(get_db)):
    try:
        return DocumentObservabilityService(db).detail(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid document UUID") from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
