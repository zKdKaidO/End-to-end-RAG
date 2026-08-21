from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.routes.internal_debug import require_debug_enabled, _generation_error
from app.db.database import get_db
from app.debug.schemas import (
    DebugRagRequest,
    DebugTrace,
    EvaluationCaseDetail,
    EvaluationCaseView,
    EvaluationComparison,
    EvaluationSummary,
)
from app.debug.services import DebugRagService, EvaluationArtifactService
from app.generation.exceptions import GenerationError


router = APIRouter(
    prefix="/internal/evaluation",
    tags=["internal-evaluation"],
    dependencies=[Depends(require_debug_enabled)],
)


def _artifacts(dataset_id: str = "legal_eval_v1") -> EvaluationArtifactService:
    try:
        return EvaluationArtifactService(dataset_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (RuntimeError, FileNotFoundError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/summary", response_model=EvaluationSummary)
def summary(dataset_id: str = Query(default="legal_eval_v1")):
    return _artifacts(dataset_id).summary()


@router.get("/cases", response_model=list[EvaluationCaseView])
def cases(dataset_id: str = Query(default="legal_eval_v1")):
    return _artifacts(dataset_id).cases()


@router.get("/cases/{case_id}", response_model=EvaluationCaseDetail)
def case_detail(case_id: str, dataset_id: str = Query(default="legal_eval_v1")):
    try:
        return _artifacts(dataset_id).case_detail(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Evaluation case not found") from exc


@router.get("/comparison", response_model=EvaluationComparison)
def comparison(dataset_id: str = Query(default="legal_eval_v1")):
    return _artifacts(dataset_id).comparison()


@router.post("/cases/{case_id}/rerun", response_model=DebugTrace)
async def rerun(case_id: str, request: Request, dataset_id: str = Query(default="legal_eval_v1"), db: Session = Depends(get_db)):
    try:
        case = _artifacts(dataset_id).dataset_case(case_id)
        payload = DebugRagRequest(
            query_text=case.question,
            document_ids=case.document_ids,
            evaluation_case_id=case.case_id,
        )
        return await DebugRagService(db).run(request.state.request_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Evaluation case not found") from exc
    except GenerationError as exc:
        raise _generation_error(exc) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"stage": "EVALUATION_RERUN", "message": "Unable to rerun evaluation case"},
        ) from exc
