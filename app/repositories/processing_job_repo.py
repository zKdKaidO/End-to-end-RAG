from sqlalchemy import select, update
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
            result = self.db.execute(
                update(DocumentProcessingJob)
                .where(
                    DocumentProcessingJob.id == uuid.UUID(job_id),
                    DocumentProcessingJob.status.in_(("PENDING", "FAILED", "PROCESSING")),
                )
                .values(status="PROCESSING", started_at=datetime.now(timezone.utc))
                .execution_options(synchronize_session=False)
            )
            self.db.commit()
            return result.rowcount == 1
        except SQLAlchemyError as e:
            self.db.rollback()
            raise DatabaseError("Failed to transition processing job to PROCESSING") from e

    def update_stage(self, job_id: str, stage: ProcessingStage) -> bool:
        try:
            result = self.db.execute(
                update(DocumentProcessingJob)
                .where(
                    DocumentProcessingJob.id == uuid.UUID(job_id),
                    DocumentProcessingJob.status == "PROCESSING",
                )
                .values(current_stage=stage.value)
                .execution_options(synchronize_session=False)
            )
            self.db.commit()
            return result.rowcount == 1
        except SQLAlchemyError as e:
            self.db.rollback()
            raise DatabaseError("Failed to update processing job stage") from e

    def update_counts(self, job_id: str, units_created: int, chunks_created: int) -> bool:
        try:
            result = self.db.execute(
                update(DocumentProcessingJob)
                .where(
                    DocumentProcessingJob.id == uuid.UUID(job_id),
                    DocumentProcessingJob.status == "PROCESSING",
                )
                .values(units_created=units_created, chunks_created=chunks_created)
                .execution_options(synchronize_session=False)
            )
            self.db.commit()
            return result.rowcount == 1
        except SQLAlchemyError as e:
            self.db.rollback()
            raise DatabaseError("Failed to update processing job counts") from e

    def mark_completed(self, job_id: str) -> bool:
        try:
            result = self.db.execute(
                update(DocumentProcessingJob)
                .where(
                    DocumentProcessingJob.id == uuid.UUID(job_id),
                    DocumentProcessingJob.status == "PROCESSING",
                )
                .values(
                    status="COMPLETED",
                    current_stage=ProcessingStage.DONE.value,
                    finished_at=datetime.now(timezone.utc),
                )
                .execution_options(synchronize_session=False)
            )
            self.db.commit()
            return result.rowcount == 1
        except SQLAlchemyError as e:
            self.db.rollback()
            raise DatabaseError("Failed to mark processing job as COMPLETED") from e

    def mark_failed(self, job_id: str, error_stage: str, error_type: str, error_message: str) -> bool:
        try:
            result = self.db.execute(
                update(DocumentProcessingJob)
                .where(DocumentProcessingJob.id == uuid.UUID(job_id))
                .values(
                    status="FAILED",
                    error_stage=error_stage,
                    error_type=error_type,
                    error_message=error_message,
                    finished_at=datetime.now(timezone.utc),
                )
                .execution_options(synchronize_session=False)
            )
            self.db.commit()
            return result.rowcount == 1
        except SQLAlchemyError as e:
            self.db.rollback()
            raise DatabaseError("Failed to mark processing job as FAILED") from e

    def document_exists(self, document_id: str) -> bool:
        from app.models.document import Document

        return self.db.scalar(
            select(Document.id).where(Document.id == uuid.UUID(document_id))
        ) is not None
