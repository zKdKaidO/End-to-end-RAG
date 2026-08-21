from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from typing import Dict
from app.api.dependencies import get_document_repo, get_job_repo, get_storage_client
from app.repositories.document_repo import DocumentRepository
from app.repositories.job_repo import JobRepository
from app.storage.minio_client import MinioClient
from app.queue.rq_client import rq_client
from app.services.upload_service import UploadService
from app.schemas.document import DocumentResponse, JobResponse
from app.core.exceptions import BaseAppException

router = APIRouter()

@router.post("/documents", response_model=Dict[str, DocumentResponse], status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    doc_repo: DocumentRepository = Depends(get_document_repo),
    job_repo: JobRepository = Depends(get_job_repo),
    storage_client: MinioClient = Depends(get_storage_client)
):
    upload_service = UploadService(doc_repo, job_repo, storage_client, rq_client)
    
    try:
        from structlog.contextvars import get_contextvars
        request_id = get_contextvars().get("request_id")
        file_bytes = await file.read()
        doc, job = upload_service.process_upload(
            file_bytes=file_bytes,
            filename=file.filename,
            mime_type=file.content_type,
            request_id=request_id
        )
        # Whether it's a deduplicated doc or new, return it wrapped
        # If deduplicated, status might be COMPLETED/PROCESSING. If new, PENDING.
        return {"document": doc}
    except BaseAppException as e:
        raise HTTPException(status_code=400, detail=str(e.message))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, doc_repo: DocumentRepository = Depends(get_document_repo)):
    doc = doc_repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@router.get("/ingestion-jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, job_repo: JobRepository = Depends(get_job_repo)):
    job = job_repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/documents/{document_id}/pages")
def get_document_pages(
    document_id: str, 
    limit: int = 10, 
    offset: int = 0,
    db = Depends(get_document_repo)
):
    from app.models.document_page import DocumentPage
    pages = db.db.query(DocumentPage)\
                 .filter(DocumentPage.document_id == document_id)\
                 .order_by(DocumentPage.page_number)\
                 .limit(limit).offset(offset).all()
    
    return {
        "data": [
            {
                "page_number": p.page_number,
                "char_count": p.char_count,
                "raw_text_snippet": p.raw_text[:100] + "..." if len(p.raw_text) > 100 else p.raw_text
            }
            for p in pages
        ],
        "pagination": {"limit": limit, "offset": offset}
    }
