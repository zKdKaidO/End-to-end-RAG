from fastapi import UploadFile
from app.db.database import SessionLocal
from app.repositories.document_repo import DocumentRepository
from app.repositories.job_repo import JobRepository
from app.storage.minio_client import MinioClient
from app.queue.rq_client import RQClient
from app.pdf.validator import validate_and_hash_pdf
from app.core.logging import get_logger
from app.models.document import DocumentStatus

logger = get_logger(__name__)

class UploadService:
    def __init__(
        self,
        document_repo: DocumentRepository,
        job_repo: JobRepository,
        storage_client: MinioClient,
        queue_client: RQClient
    ):
        self.doc_repo = document_repo
        self.job_repo = job_repo
        self.storage_client = storage_client
        self.queue_client = queue_client

    def process_upload(self, file_bytes: bytes, filename: str, mime_type: str, request_id: str = None, on_document_resolved=None):
        # 1. Validate and Hash
        _, sha256 = validate_and_hash_pdf(file_bytes, filename, mime_type)
        
        # 2. Deduplication check
        existing_doc = self.doc_repo.get_by_sha256(sha256)
        if existing_doc:
            if on_document_resolved:
                on_document_resolved(existing_doc)
            logger.info("document_deduplicated", sha256=sha256, document_id=str(existing_doc.id))
            return existing_doc, None # Return existing doc, no new job

        # 3. Register Document (Status: UPLOADING)
        # Using try-except for IntegrityError race condition is standard, but repo doesn't catch it currently.
        # SQLAlchemy will throw IntegrityError if a concurrent upload inserts the same sha256.
        # We will let it bubble up and handle it in the router if necessary, or just fail for now.
        try:
            doc = self.doc_repo.create(filename, mime_type, len(file_bytes), sha256)
        except Exception as exc:
            from sqlalchemy.exc import IntegrityError
            if not isinstance(exc, IntegrityError):
                raise
            self.doc_repo.db.rollback()
            doc = self.doc_repo.get_by_sha256(sha256)
            if doc is None:
                raise
            if on_document_resolved:
                on_document_resolved(doc)
            logger.info("document_deduplicated_after_race", sha256=sha256, document_id=str(doc.id))
            return doc, None
        doc_id = str(doc.id)
        if on_document_resolved:
            on_document_resolved(doc)
        
        try:
            # 4. Upload to MinIO
            storage_uri = self.storage_client.upload_pdf(doc_id, file_bytes)
            self.doc_repo.update_storage_uri(doc_id, storage_uri)
            
            # 5. Create Job (Stage: QUEUE)
            job = self.job_repo.create_job(doc_id)
            job_id = str(job.id)
            
            # 6. Enqueue Job
            try:
                self.queue_client.enqueue_ingestion_job(job_id, doc_id, request_id)
            except Exception as e:
                # Enqueue failed: Mark job and document as FAILED
                self.job_repo.mark_failed(job_id, error_stage="QUEUE", error_type="QueueError", error_message=str(e))
                raise
                
            # 7. Transition to PENDING
            success = self.job_repo.transition_to_pending(job_id)
            if not success:
                logger.warning("transition_to_pending_failed_or_skipped", job_id=job_id)

            # Refresh doc to get latest status
            self.doc_repo.db.refresh(doc)
            return doc, job
            
        except Exception as e:
            logger.error("upload_process_failed", document_id=doc_id, error=str(e))
            self.doc_repo.update_status(doc_id, DocumentStatus.FAILED)
            raise
