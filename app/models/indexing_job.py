import uuid
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

class IndexingJob(Base):
    __tablename__ = "indexing_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)

    status = Column(String, nullable=False, default="PENDING")
    current_stage = Column(String, nullable=False, default="QUEUE")

    chunks_total = Column(Integer, nullable=True)
    chunks_indexed = Column(Integer, nullable=True)

    embedding_model = Column(String, nullable=True)
    index_version = Column(String, nullable=True)

    error_stage = Column(String, nullable=True)
    error_type = Column(String, nullable=True)
    error_message = Column(String, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    document = relationship("Document")
