from datetime import datetime, timezone
from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Tuple
from app.models.document_reconstruction import DocumentReconstruction
from app.models.legal_unit import LegalUnit
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.document_processing_job import DocumentProcessingJob, ProcessingStage
from app.models.auth import DocumentAccessGrant, GlobalDocumentAccess
from app.processing.parser import LegalUnitData
from app.core.exceptions import DatabaseError
import uuid


# Deterministic integration tests replace this no-op with a barrier callback.
# Production never assigns it; the callback runs only after the short-lived
# lifecycle locks have been acquired and before any derived row is written.
LIFECYCLE_TEST_HOOK = None

class ProcessingRepository:
    def __init__(self, db: Session):
        self.db = db
        
    def save_processing_results(
        self,
        processing_job_id: str,
        document_id: str,
        normalized_text: str,
        page_offset_map: List[Dict[str, Any]],
        root_units: List[LegalUnitData],
        chunk_dicts: List[Dict[str, Any]],
    ) -> Tuple[int, int, bool] | None:
        try:
            # CPU transformation is complete before this method is entered. End
            # any read transaction, then serialize the short durable boundary
            # with canonical GC using the same Document row lock.
            self.db.rollback()
            document_uuid = uuid.UUID(document_id)
            processing_job_uuid = uuid.UUID(processing_job_id)
            document = self.db.scalar(
                select(Document).where(Document.id == document_uuid).with_for_update()
            )
            if document is None:
                self.db.rollback()
                return None

            job = self.db.scalar(
                select(DocumentProcessingJob)
                .where(
                    DocumentProcessingJob.id == processing_job_uuid,
                    DocumentProcessingJob.document_id == document_uuid,
                    DocumentProcessingJob.status == "PROCESSING",
                )
                .with_for_update()
            )
            if job is None:
                self.db.rollback()
                raise DatabaseError(
                    "Processing lifecycle conflict: canonical document exists but active job is unavailable"
                )

            if LIFECYCLE_TEST_HOOK is not None:
                LIFECYCLE_TEST_HOOK("PERSISTENCE_LOCKED", document_id, processing_job_id)

            # Idempotency: Delete existing derived data sequentially in one transaction
            self.db.query(Chunk).filter_by(document_id=document_uuid).delete()
            self.db.query(LegalUnit).filter_by(document_id=document_uuid).delete()
            self.db.query(DocumentReconstruction).filter_by(document_id=document_uuid).delete()
            
            # Save Reconstruction
            recon = DocumentReconstruction(
                document_id=document_uuid,
                normalized_text=normalized_text,
                page_offset_map=page_offset_map
            )
            self.db.add(recon)
            
            units_created = 0
            
            # Save units recursively
            def save_unit_recursive(data: LegalUnitData, parent_id: uuid.UUID = None) -> uuid.UUID:
                nonlocal units_created
                db_unit = LegalUnit(
                    document_id=document_uuid,
                    parent_unit_id=parent_id,
                    unit_type=data.unit_type,
                    unit_number=data.unit_number,
                    unit_title=data.title,
                    content_text="[See Chunks]",
                    page_start=getattr(data, "page_start", 1),
                    page_end=getattr(data, "page_end", 1),
                    char_start=data.start_char,
                    char_end=data.end_char,
                    level=data.level
                )
                self.db.add(db_unit)
                self.db.flush() # To get ID
                units_created += 1
                
                # Attach id to data object so chunks can reference it
                data.db_id = db_unit.id
                
                for child in data.children:
                    save_unit_recursive(child, db_unit.id)
                    
                return db_unit.id
                
            for u in root_units:
                save_unit_recursive(u, None)
                
            # Save chunks
            chunks_created = 0
            for c in chunk_dicts:
                db_chunk = Chunk(
                    document_id=document_uuid,
                    legal_unit_id=c["legal_unit"].db_id if "legal_unit" in c else None,
                    chunk_index=c["chunk_index"],
                    content_text=c["content_text"],
                    embedding_text=c["embedding_text"],
                    page_start=c.get("page_start", 1),
                    page_end=c.get("page_end", 1),
                    metadata_json=c.get("metadata_json", {}),
                    provenance_json=c.get("provenance_json", {})
                )
                self.db.add(db_chunk)
                chunks_created += 1
                
            # Completion is part of the same lifecycle-guarded transaction; no
            # stale ORM job is finalized after canonical deletion.
            job.units_created = units_created
            job.chunks_created = chunks_created
            job.status = "COMPLETED"
            job.current_stage = ProcessingStage.DONE.value
            job.finished_at = datetime.now(timezone.utc)
            has_access_reference = bool(self.db.scalar(select(or_(
                exists(select(1).where(DocumentAccessGrant.document_id == document_uuid)),
                exists(select(1).where(GlobalDocumentAccess.document_id == document_uuid)),
            ))))
            self.db.commit()
            return units_created, chunks_created, has_access_reference
        except Exception:
            self.db.rollback()
            raise
