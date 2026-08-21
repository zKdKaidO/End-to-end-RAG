from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
import uuid
from datetime import datetime, timezone
from app.db.base import Base

class ProcessingStage(str, enum.Enum):
    CLEANING = "CLEANING"
    HEADER_FOOTER_REMOVAL = "HEADER_FOOTER_REMOVAL"
    RECONSTRUCTION = "RECONSTRUCTION"
    METADATA_EXTRACTION = "METADATA_EXTRACTION"
    LEGAL_PARSING = "LEGAL_PARSING"
    CHUNKING = "CHUNKING"
    PERSISTENCE = "PERSISTENCE"
    DONE = "DONE"

class DocumentProcessingJob(Base):
    __tablename__ = "document_processing_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), nullable=False, default="PENDING")
    current_stage = Column(String(50), nullable=True)
    units_created = Column(Integer, default=0)
    chunks_created = Column(Integer, default=0)
    error_stage = Column(String(50), nullable=True)
    error_type = Column(String(255), nullable=True)
    error_message = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    
    document = relationship("Document")
