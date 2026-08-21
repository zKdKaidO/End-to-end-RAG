import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base

class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    
    # We duplicate status here for worker tracking, but keep it in sync with Document
    status = Column(String, default="UPLOADING", nullable=False) 
    current_stage = Column(String, nullable=True)
    
    pages_total = Column(Integer, default=0)
    pages_processed = Column(Integer, default=0)
    
    error_stage = Column(String, nullable=True)
    error_type = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    # Relationships
    document = relationship("Document", back_populates="jobs")
