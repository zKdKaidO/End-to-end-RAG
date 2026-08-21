import os
import sys
from rq import Worker, Queue
from rq import get_current_job
from redis import Redis
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.db.database import SessionLocal
from app.repositories.document_repo import DocumentRepository
from app.repositories.job_repo import JobRepository
from app.storage.minio_client import minio_client
from app.models.document import DocumentStatus
from app.core.exceptions import ObjectStorageError
from app.pdf.extractor import PDFExtractor

setup_logging()
logger = get_logger(__name__)

def process_ingestion(job_id: str, document_id: str, request_id: str = None):
    from structlog.contextvars import clear_contextvars, bind_contextvars
    clear_contextvars()
    if request_id:
        bind_contextvars(request_id=request_id)
    bind_contextvars(job_id=job_id, document_id=document_id)
    
    logger.info("job_started", job_id=job_id, document_id=document_id)
    db = SessionLocal()
    try:
        doc_repo = DocumentRepository(db)
        job_repo = JobRepository(db)
        
        # 1. Transition to PROCESSING
        job = job_repo.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found in DB")
            
        job.status = "PROCESSING"
        job.current_stage = "DOWNLOAD"
        db.commit()

        doc_repo.update_status(document_id, DocumentStatus.PROCESSING)
        
        # 2. Download PDF
        try:
            pdf_bytes = minio_client.download_pdf(document_id)
            logger.info("pdf_downloaded", document_id=document_id, size=len(pdf_bytes))
        except ObjectStorageError as e:
            # Re-raise to trigger RQ retry
            raise
            
        # 3. Extract pages and persist in batches
        job.current_stage = "TEXT_EXTRACTION"
        db.commit()
        
        from app.repositories.page_repo import PageRepository
        page_repo = PageRepository(db)
        
        batch = []
        BATCH_SIZE = 25
        total_pages = 0
        
        extractor = PDFExtractor()
        for page_data in extractor.extract_pages(pdf_bytes):
            batch.append(page_data)
            total_pages += 1
            if len(batch) >= BATCH_SIZE:
                page_repo.batch_upsert_pages(document_id, job_id, batch)
                batch = []
        
        if batch:
            page_repo.batch_upsert_pages(document_id, job_id, batch)
            
        job.pages_total = total_pages
        job.status = "COMPLETED"
        job.current_stage = "DONE"
        doc_repo.update_status(document_id, DocumentStatus.COMPLETED)
        db.commit()
        logger.info("job_completed", job_id=job_id, pages_total=total_pages)
        
        # Block 2 Integration Hook
        from app.repositories.processing_job_repo import ProcessingJobRepository
        from app.queue.rq_client import rq_client
        p_repo = ProcessingJobRepository(db)
        p_job = p_repo.get_by_document_id(document_id)
        if not p_job:
            p_job = p_repo.create_job(document_id)
        # Check if it's already completed? If it's a retry of Block 1 we don't want to double queue.
        # But if it's a clean run, it will be PENDING.
        if p_job.status in ("PENDING", "FAILED"):
            rq_client.enqueue_document_processing_job(str(p_job.id), document_id, request_id)
        
    except Exception as e:
        logger.error("job_failed_attempt", job_id=job_id, error=str(e))
        db.rollback()
        
        rq_job = get_current_job()
        
        # retries_left is the number of retries remaining *after* this failure if we raise
        # Actually in rq, retries_left is decremented *before* the job executes.
        # If max=2, on first run retries_left=2. Second run=1. Third run=0.
        # If it's 0, this is the final attempt.
        if rq_job and (rq_job.retries_left is None or rq_job.retries_left == 0):
            logger.error("job_terminal_failure", job_id=job_id)
            job_repo = JobRepository(db)
            job_repo.mark_failed(
                job_id, 
                error_stage=job_repo.get_by_id(job_id).current_stage or "UNKNOWN", 
                error_type=type(e).__name__, 
                error_message=str(e)
            )
            
        raise # ALWAYS RAISE so RQ knows it failed and handles retry/failed queue
    finally:
        db.close()

def run_worker():
    redis_conn = Redis.from_url(settings.REDIS_URL)
    qs = [Queue('ingestion', connection=redis_conn)]
    w = Worker(qs, connection=redis_conn)
    logger.info("Worker process starting up...", queues='ingestion')
    w.work()

if __name__ == "__main__":
    run_worker()
