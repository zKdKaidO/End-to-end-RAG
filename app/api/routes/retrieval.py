from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.database import get_db
from app.retrieval.exceptions import (
    RetrievalDependencyError,
    RetrievalError,
    RetrievalValidationError,
)
from app.retrieval.schemas import RetrievalRequest, RetrievalResponse
from app.retrieval.service import RetrievalService, validate_request
from app.auth.dependencies import require_authenticated_user
from app.auth.principal import Principal
from app.auth.scope import UserRetrievalScope


router = APIRouter(tags=["retrieval"])
logger = get_logger(__name__)


def get_retrieval_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_authenticated_user),
) -> RetrievalService:
    return RetrievalService(db, access_scope=UserRetrievalScope(principal.user_id))


@router.post("/retrieve", response_model=RetrievalResponse)
def retrieve(
    payload: dict[str, Any] = Body(...),
    service: RetrievalService = Depends(get_retrieval_service),
):
    try:
        request = RetrievalRequest.model_validate(payload)
        params = validate_request(request)
        require_scope = getattr(service, "require_document_scope", None)
        if require_scope is not None:
            require_scope(params.document_ids)
        return {"results": service.retrieve(params)}
    except ValidationError as exc:
        message = "; ".join(error["msg"] for error in exc.errors())
        logger.info("retrieval_validation_rejected", stage="VALIDATE_QUERY", error=message)
        raise HTTPException(
            status_code=400,
            detail={"stage": "VALIDATE_QUERY", "message": message},
        ) from exc
    except RetrievalValidationError as exc:
        logger.info("retrieval_validation_rejected", stage=exc.stage, error=exc.message)
        raise HTTPException(
            status_code=400,
            detail={"stage": exc.stage, "message": exc.message},
        ) from exc
    except RetrievalDependencyError as exc:
        logger.error("retrieval_dependency_error", stage=exc.stage, error=exc.message)
        raise HTTPException(
            status_code=503,
            detail={"stage": exc.stage, "message": exc.message},
        ) from exc
    except RetrievalError as exc:
        logger.exception("retrieval_internal_error", stage=exc.stage)
        raise HTTPException(
            status_code=500,
            detail={"stage": exc.stage, "message": exc.message},
        ) from exc
