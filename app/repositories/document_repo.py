from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.document import Document, DocumentStatus
from app.core.exceptions import DuplicateDocumentError

class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, document_id: str) -> Optional[Document]:
        return self.db.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()

    def get_by_sha256(self, sha256: str) -> Optional[Document]:
        return self.db.execute(select(Document).where(Document.sha256 == sha256)).scalar_one_or_none()

    def create(self, filename: str, mime_type: str, file_size: int, sha256: str) -> Document:
        doc = Document(
            filename=filename,
            mime_type=mime_type,
            file_size=file_size,
            sha256=sha256,
            status=DocumentStatus.UPLOADING
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def update_storage_uri(self, document_id: str, storage_uri: str) -> Optional[Document]:
        doc = self.get_by_id(document_id)
        if doc:
            doc.storage_uri = storage_uri
            self.db.commit()
            self.db.refresh(doc)
        return doc

    def update_status(self, document_id: str, status: DocumentStatus) -> Optional[Document]:
        doc = self.get_by_id(document_id)
        if doc:
            doc.status = status
            self.db.commit()
            self.db.refresh(doc)
        return doc
