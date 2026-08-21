from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.models.document_processing_job import DocumentProcessingJob, ProcessingStage
from app.core.exceptions import DatabaseError
from datetime import datetime, timezone
import uuid

class ProcessingJobRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_job(self, document_id: str) -> DocumentProcessingJob:
        try:
            job = DocumentProcessingJob(
                document_id=uuid.UUID(document_id),
                status="PENDING",
                units_created=0,
                chunks_created=0
            )
            self.db.add(job)
            self.db.commit()
            self.db.refresh(job)
            return job
        except SQLAlchemyError as e:
            self.db.rollback()
            raise DatabaseError("Failed to create processing job") from e

    def get_by_id(self, job_id: str) -> DocumentProcessingJob:
        return self.db.query(DocumentProcessingJob).filter(DocumentProcessingJob.id == uuid.UUID(job_id)).first()

    def get_by_document_id(self, document_id: str) -> DocumentProcessingJob:
        return self.db.query(DocumentProcessingJob).filter(DocumentProcessingJob.document_id == uuid.UUID(document_id)).first()

    def transition_to_processing(self, job_id: str) -> bool:
        try:
            job = self.db.query(DocumentProcessingJob).with_for_update().filter(DocumentProcessingJob.id == uuid.UUID(job_id)).first()
            if not job:
                return False
            if job.status in ("PENDING", "FAILED", "PROCESSING"):
                job.status = "PROCESSING"
                job.started_at = datetime.now(timezone.utc)
                self.db.commit()
                return True
            self.db.commit()
            return False
        except SQLAlchemyError as e:
            self.db.rollback()
            raise DatabaseError("Failed to transition processing job to PROCESSING") from e

    def update_stage(self, job_id: str, stage: ProcessingStage) -> None:
        try:
            job = self.db.query(DocumentProcessingJob).filter(DocumentProcessingJob.id == uuid.UUID(job_id)).first()
            if job:
                job.current_stage = stage.value
                self.db.commit()
        except SQLAlchemyError as e:
            self.db.rollback()
            raise DatabaseError("Failed to update processing job stage") from e

    def update_counts(self, job_id: str, units_created: int, chunks_created: int) -> None:
        try:
            job = self.db.query(DocumentProcessingJob).filter(DocumentProcessingJob.id == uuid.UUID(job_id)).first()
            if job:
                job.units_created = units_created
                job.chunks_created = chunks_created
                self.db.commit()
        except SQLAlchemyError as e:
            self.db.rollback()
            raise DatabaseError("Failed to update processing job counts") from e

    def mark_completed(self, job_id: str) -> None:
        try:
            job = self.db.query(DocumentProcessingJob).filter(DocumentProcessingJob.id == uuid.UUID(job_id)).first()
            if job:
                job.status = "COMPLETED"
                job.current_stage = ProcessingStage.DONE.value
                job.finished_at = datetime.now(timezone.utc)
                self.db.commit()
        except SQLAlchemyError as e:
            self.db.rollback()
            raise DatabaseError("Failed to mark processing job as COMPLETED") from e

    def mark_failed(self, job_id: str, error_stage: str, error_type: str, error_message: str) -> None:
        try:
            job = self.db.query(DocumentProcessingJob).filter(DocumentProcessingJob.id == uuid.UUID(job_id)).first()
            if job:
                job.status = "FAILED"
                job.error_stage = error_stage
                job.error_type = error_type
                job.error_message = error_message
                job.finished_at = datetime.now(timezone.utc)
                self.db.commit()
        except SQLAlchemyError as e:
            self.db.rollback()
            raise DatabaseError("Failed to mark processing job as FAILED") from e
