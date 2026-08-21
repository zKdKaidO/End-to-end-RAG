from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timezone
from app.db.base import Base

class LegalUnit(Base):
    __tablename__ = "legal_units"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    parent_unit_id = Column(UUID(as_uuid=True), ForeignKey("legal_units.id", ondelete="CASCADE"), nullable=True)
    unit_type = Column(String(50), nullable=False)
    unit_number = Column(String(50), nullable=True)
    unit_title = Column(String, nullable=True)
    content_text = Column(String, nullable=False)
    page_start = Column(Integer, nullable=False)
    page_end = Column(Integer, nullable=False)
    char_start = Column(Integer, nullable=False)
    char_end = Column(Integer, nullable=False)
    level = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    document = relationship("Document")
    parent = relationship("LegalUnit", remote_side=[id], backref="children")
