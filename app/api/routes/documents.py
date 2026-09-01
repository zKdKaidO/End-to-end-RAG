import uuid
from typing import Dict, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_document_repo, get_job_repo, get_storage_client
from app.auth.access import DocumentAccessService, RESOURCE_NOT_FOUND
from app.auth.dependencies import require_admin, require_authenticated_user
from app.auth.principal import Principal
from app.core.exceptions import BaseAppException
from app.db.database import get_db
from app.debug.services import DocumentObservabilityService
from app.models.auth import UserRole
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.queue.rq_client import rq_client
from app.repositories.document_repo import DocumentRepository
from app.repositories.job_repo import JobRepository
from app.schemas.document import DocumentResponse, JobResponse
from app.services.upload_service import UploadService
from app.storage.minio_client import MinioClient
from app.core.config import settings
from app.deployment.barrier import cross_store_barrier


router = APIRouter()


async def read_upload_limited(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                413,
                detail={"error_code": "UPLOAD_TOO_LARGE", "message": f"Upload exceeds the limit of {settings.MAX_UPLOAD_SIZE} bytes."},
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/documents", response_model=Dict[str, DocumentResponse], status_code=202)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    access: Literal["private", "global"] = Query(default="private"),
    principal: Principal = Depends(require_authenticated_user),
    doc_repo: DocumentRepository = Depends(get_document_repo),
    job_repo: JobRepository = Depends(get_job_repo),
    storage_client: MinioClient = Depends(get_storage_client),
):
    if access == "global" and principal.role != UserRole.ADMIN.value:
        raise HTTPException(403, detail={"error_code": "FORBIDDEN", "message": "Administrator access required."})
    upload_service = UploadService(doc_repo, job_repo, storage_client, rq_client)
    access_service = DocumentAccessService(doc_repo.db)

    def grant(document: Document) -> None:
        if access == "global":
            access_service.grant_global(principal.user_id, document.id)
        else:
            access_service.grant_private(principal.user_id, document.id)

    try:
        file_bytes = await read_upload_limited(file)
        with cross_store_barrier(exclusive=False):
            doc, _job = upload_service.process_upload(
                file_bytes=file_bytes,
                filename=file.filename or "document.pdf",
                # An absent declaration is not evidence of a PDF. The structural
                # parser still provides the authoritative byte-level check.
                mime_type=file.content_type or "",
                request_id=request.state.request_id,
                on_document_resolved=grant,
            )
        return {"document": doc}
    except BaseAppException as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal Server Error") from exc


@router.get("/documents")
def list_documents(
    principal: Principal = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
    access_service = DocumentAccessService(db)
    ids = db.scalars(
        select(Document.id)
        .where(access_service.predicate(principal.user_id, Document.id))
        .order_by(Document.created_at.desc(), Document.id.desc())
    ).all()
    observability = DocumentObservabilityService(db)
    data = []
    for document_id in ids:
        item = observability.detail(str(document_id)).model_dump(mode="json")
        item["access_origin"] = access_service.access_origin(principal.user_id, document_id)
        data.append(item)
    return data


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: uuid.UUID,
    principal: Principal = Depends(require_authenticated_user),
    doc_repo: DocumentRepository = Depends(get_document_repo),
):
    DocumentAccessService(doc_repo.db).require_accessible(principal.user_id, document_id)
    doc = doc_repo.get_by_id(str(document_id))
    if not doc:
        raise HTTPException(status_code=404, detail=RESOURCE_NOT_FOUND)
    return doc


@router.get("/api/v1/documents/{document_id}")
def document_detail(
    document_id: uuid.UUID,
    principal: Principal = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
    access = DocumentAccessService(db)
    access.require_accessible(principal.user_id, document_id)
    item = DocumentObservabilityService(db).detail(str(document_id)).model_dump(mode="json")
    item["access_origin"] = access.access_origin(principal.user_id, document_id)
    return item


@router.get("/api/v1/chunks/{chunk_id}")
def chunk_detail(
    chunk_id: uuid.UUID,
    principal: Principal = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
    chunk = db.scalar(select(Chunk).where(Chunk.id == chunk_id))
    if chunk is None:
        raise HTTPException(404, detail=RESOURCE_NOT_FOUND)
    DocumentAccessService(db).require_accessible(principal.user_id, chunk.document_id)
    return {
        "chunk_id": str(chunk.id), "document_id": str(chunk.document_id),
        "legal_unit_id": str(chunk.legal_unit_id) if chunk.legal_unit_id else None,
        "content_text": chunk.content_text, "embedding_text": chunk.embedding_text,
        "metadata_json": chunk.metadata_json, "provenance_json": chunk.provenance_json,
        "page_start": chunk.page_start, "page_end": chunk.page_end,
    }


@router.get("/ingestion-jobs/{job_id}", response_model=JobResponse)
def get_job(
    job_id: uuid.UUID,
    principal: Principal = Depends(require_authenticated_user),
    job_repo: JobRepository = Depends(get_job_repo),
):
    job = job_repo.get_by_id(str(job_id))
    if not job:
        raise HTTPException(status_code=404, detail=RESOURCE_NOT_FOUND)
    DocumentAccessService(job_repo.db).require_accessible(principal.user_id, job.document_id)
    return job


@router.get("/documents/{document_id}/pages")
def get_document_pages(
    document_id: uuid.UUID,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
    DocumentAccessService(db).require_accessible(principal.user_id, document_id)
    pages = db.scalars(
        select(DocumentPage).where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number).limit(limit).offset(offset)
    ).all()
    return {
        "data": [{
            "page_number": page.page_number, "char_count": page.char_count,
            "raw_text_snippet": page.raw_text[:100] + "..." if len(page.raw_text) > 100 else page.raw_text,
        } for page in pages],
        "pagination": {"limit": limit, "offset": offset},
    }


@router.delete("/documents/{document_id}", status_code=202)
def remove_private_access(
    document_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
    removed, orphaned = DocumentAccessService(db).revoke_from_library(
        principal.user_id, principal.role, document_id
    )
    if orphaned:
        try:
            rq_client.enqueue_document_gc(str(document_id), request.state.request_id)
        except Exception:
            pass
    return {"access_removed": removed, "gc_candidate": orphaned}


@router.post("/api/v1/admin/documents/{document_id}/global-access", status_code=201)
def grant_global_access(
    document_id: uuid.UUID,
    principal: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
):
    DocumentAccessService(db).grant_global(principal.user_id, document_id)
    return {"document_id": str(document_id), "access": "GLOBAL"}


@router.delete("/api/v1/admin/documents/{document_id}/global-access", status_code=202)
def revoke_global_access(
    document_id: uuid.UUID,
    request: Request,
    _principal: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
):
    orphaned = DocumentAccessService(db).revoke_global(document_id)
    if orphaned:
        try:
            rq_client.enqueue_document_gc(str(document_id), request.state.request_id)
        except Exception:
            pass
    return {"access_removed": "GLOBAL", "gc_candidate": orphaned}
