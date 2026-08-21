from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from app.models.ingestion_job import IngestionJob
from app.models.document import Document, DocumentStatus

class JobRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, job_id: str) -> Optional[IngestionJob]:
        return self.db.execute(select(IngestionJob).where(IngestionJob.id == job_id)).scalar_one_or_none()

    def create_job(self, document_id: str) -> IngestionJob:
        job = IngestionJob(
            document_id=document_id,
            status="UPLOADING",
            current_stage="QUEUE"
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def transition_to_pending(self, job_id: str) -> bool:
        # Atomic transition to prevent race condition: only update if it is UPLOADING
        job = self.db.execute(
            select(IngestionJob).where(and_(IngestionJob.id == job_id, IngestionJob.status == "UPLOADING"))
        ).scalar_one_or_none()
        
        if job:
            job.status = "PENDING"
            # Keep document status in sync
            doc = self.db.execute(select(Document).where(Document.id == job.document_id)).scalar_one_or_none()
            if doc:
                doc.status = DocumentStatus.PENDING
            self.db.commit()
            return True
        return False

    def mark_failed(self, job_id: str, error_stage: str, error_type: str, error_message: str):
        job = self.get_by_id(job_id)
        if job:
            job.status = "FAILED"
            job.error_stage = error_stage
            job.error_type = error_type
            job.error_message = error_message
            job.finished_at = datetime.now(timezone.utc)
            
            doc = self.db.execute(select(Document).where(Document.id == job.document_id)).scalar_one_or_none()
            if doc:
                doc.status = DocumentStatus.FAILED
            
            self.db.commit()
