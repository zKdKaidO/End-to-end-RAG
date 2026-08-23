from pydantic import BaseModel, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime

class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    status: str
    sha256: str
    page_count: Optional[int]
    created_at: datetime
    
    class Config:
        from_attributes = True

class JobResponse(BaseModel):
    id: UUID
    document_id: UUID
    status: str
    current_stage: Optional[str]
    pages_processed: int
    pages_total: int
    error_message: Optional[str]

    @field_validator("error_message")
    @classmethod
    def sanitize_error(cls, value):
        from app.security.errors import safe_public_job_error
        return safe_public_job_error(value)

    class Config:
        from_attributes = True
