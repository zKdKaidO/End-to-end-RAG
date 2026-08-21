from sqlalchemy.orm import Session
from sqlalchemy import select, update
from datetime import datetime
from app.models.indexing_job import IndexingJob

class IndexingJobRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_job(self, document_id: str, index_version: str, embedding_model: str) -> IndexingJob:
        job = IndexingJob(
            document_id=document_id,
            status="PENDING",
            current_stage="QUEUE",
            index_version=index_version,
            embedding_model=embedding_model
        )
        self.db.add(job)
        self.db.commit()
        return job

    def get_by_id(self, job_id: str) -> IndexingJob:
        return self.db.execute(
            select(IndexingJob).where(IndexingJob.id == job_id)
        ).scalar_one_or_none()

    def get_active_job_for_document(self, document_id: str, index_version: str) -> IndexingJob:
        return self.db.execute(
            select(IndexingJob).where(
                IndexingJob.document_id == document_id,
                IndexingJob.index_version == index_version,
                IndexingJob.status.in_(["PENDING", "PROCESSING"])
            )
        ).scalar_one_or_none()

    def transition_to_processing(self, job_id: str):
        stmt = update(IndexingJob).where(
            IndexingJob.id == job_id,
            IndexingJob.status.in_(["PENDING", "FAILED", "PROCESSING"])
        ).values(
            status="PROCESSING",
            current_stage="LOAD_CHUNKS",
            started_at=datetime.utcnow()
        )
        self.db.execute(stmt)
        self.db.commit()

    def update_stage(self, job_id: str, stage: str):
        stmt = update(IndexingJob).where(
            IndexingJob.id == job_id
        ).values(
            current_stage=stage
        )
        self.db.execute(stmt)
        self.db.commit()
        
    def update_counts(self, job_id: str, chunks_total: int = None, chunks_indexed: int = None):
        values = {}
        if chunks_total is not None:
            values["chunks_total"] = chunks_total
        if chunks_indexed is not None:
            values["chunks_indexed"] = chunks_indexed
            
        if values:
            stmt = update(IndexingJob).where(IndexingJob.id == job_id).values(**values)
            self.db.execute(stmt)
            self.db.commit()

    def mark_completed(self, job_id: str):
        stmt = update(IndexingJob).where(
            IndexingJob.id == job_id
        ).values(
            status="COMPLETED",
            finished_at=datetime.utcnow()
        )
        self.db.execute(stmt)
        self.db.commit()

    def mark_failed(self, job_id: str, error_stage: str, error_type: str, error_message: str):
        stmt = update(IndexingJob).where(
            IndexingJob.id == job_id
        ).values(
            status="FAILED",
            error_stage=error_stage,
            error_type=error_type,
            error_message=error_message,
            finished_at=datetime.utcnow()
        )
        self.db.execute(stmt)
        self.db.commit()
