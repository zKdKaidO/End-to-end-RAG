from pydantic import BaseModel
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

    class Config:
        from_attributes = True
