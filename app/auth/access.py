import uuid
from collections.abc import Sequence

from fastapi import HTTPException
from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy.orm import Session

from app.models.auth import DocumentAccessGrant, GlobalDocumentAccess
from app.models.document import Document


RESOURCE_NOT_FOUND = {"error_code": "RESOURCE_NOT_FOUND", "message": "Resource not found."}


class DocumentAccessService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def predicate(user_id: uuid.UUID, document_column):
        return or_(
            exists(select(1).where(DocumentAccessGrant.document_id == document_column, DocumentAccessGrant.user_id == user_id)),
            exists(select(1).where(GlobalDocumentAccess.document_id == document_column)),
        )

    def is_accessible(self, user_id: uuid.UUID, document_id: uuid.UUID) -> bool:
        return bool(self.db.scalar(select(self.predicate(user_id, document_id))))

    def require_accessible(self, user_id: uuid.UUID, document_id: uuid.UUID) -> None:
        visible = self.db.scalar(
            select(Document.id).where(Document.id == document_id, self.predicate(user_id, Document.id))
        )
        if visible is None:
            raise HTTPException(404, detail=RESOURCE_NOT_FOUND)

    def require_all_accessible(self, user_id: uuid.UUID, document_ids: Sequence[uuid.UUID]) -> None:
        ids = tuple(dict.fromkeys(document_ids))
        if not ids:
            return
        visible = self.db.scalar(
            select(func.count(Document.id)).where(Document.id.in_(ids), self.predicate(user_id, Document.id))
        )
        if visible != len(ids):
            raise HTTPException(404, detail=RESOURCE_NOT_FOUND)

    def grant_private(self, user_id: uuid.UUID, document_id: uuid.UUID) -> None:
        document = self.db.scalar(select(Document).where(Document.id == document_id).with_for_update())
        if document is None:
            raise HTTPException(404, detail=RESOURCE_NOT_FOUND)
        if self.db.get(DocumentAccessGrant, (document_id, user_id)) is None:
            self.db.add(DocumentAccessGrant(document_id=document_id, user_id=user_id))
        self.db.commit()

    def grant_global(self, admin_user_id: uuid.UUID, document_id: uuid.UUID) -> None:
        document = self.db.scalar(select(Document).where(Document.id == document_id).with_for_update())
        if document is None:
            raise HTTPException(404, detail=RESOURCE_NOT_FOUND)
        if self.db.get(GlobalDocumentAccess, document_id) is None:
            self.db.add(GlobalDocumentAccess(document_id=document_id, granted_by_user_id=admin_user_id))
        self.db.commit()

    def revoke_private(self, user_id: uuid.UUID, document_id: uuid.UUID) -> bool:
        document = self.db.scalar(select(Document).where(Document.id == document_id).with_for_update())
        if document is None:
            raise HTTPException(404, detail=RESOURCE_NOT_FOUND)
        result = self.db.execute(delete(DocumentAccessGrant).where(
            DocumentAccessGrant.document_id == document_id, DocumentAccessGrant.user_id == user_id
        ))
        if result.rowcount == 0:
            self.db.rollback()
            raise HTTPException(404, detail=RESOURCE_NOT_FOUND)
        orphaned = not self._has_references(document_id)
        self.db.commit()
        return orphaned

    def revoke_global(self, document_id: uuid.UUID) -> bool:
        document = self.db.scalar(select(Document).where(Document.id == document_id).with_for_update())
        if document is None:
            raise HTTPException(404, detail=RESOURCE_NOT_FOUND)
        result = self.db.execute(delete(GlobalDocumentAccess).where(GlobalDocumentAccess.document_id == document_id))
        if result.rowcount == 0:
            self.db.rollback()
            raise HTTPException(404, detail=RESOURCE_NOT_FOUND)
        orphaned = not self._has_references(document_id)
        self.db.commit()
        return orphaned

    def _has_references(self, document_id: uuid.UUID) -> bool:
        return bool(self.db.scalar(select(or_(
            exists(select(1).where(DocumentAccessGrant.document_id == document_id)),
            exists(select(1).where(GlobalDocumentAccess.document_id == document_id)),
        ))))

    def access_origin(self, user_id: uuid.UUID, document_id: uuid.UUID) -> str | None:
        private = self.db.get(DocumentAccessGrant, (document_id, user_id)) is not None
        global_access = self.db.get(GlobalDocumentAccess, document_id) is not None
        if private and global_access:
            return "PRIVATE + GLOBAL"
        if private:
            return "PRIVATE"
        if global_access:
            return "GLOBAL"
        return None
