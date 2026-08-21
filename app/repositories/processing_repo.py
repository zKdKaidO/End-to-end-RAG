from sqlalchemy.orm import Session
from typing import List, Dict, Any, Tuple
from app.models.document_reconstruction import DocumentReconstruction
from app.models.legal_unit import LegalUnit
from app.models.chunk import Chunk
from app.processing.parser import LegalUnitData
import uuid

class ProcessingRepository:
    def __init__(self, db: Session):
        self.db = db
        
    def save_processing_results(self, document_id: str, normalized_text: str, page_offset_map: List[Dict[str, Any]], root_units: List[LegalUnitData], chunk_dicts: List[Dict[str, Any]]) -> Tuple[int, int]:
        try:
            # Idempotency: Delete existing derived data sequentially in one transaction
            self.db.query(Chunk).filter_by(document_id=uuid.UUID(document_id)).delete()
            self.db.query(LegalUnit).filter_by(document_id=uuid.UUID(document_id)).delete()
            self.db.query(DocumentReconstruction).filter_by(document_id=uuid.UUID(document_id)).delete()
            
            # Save Reconstruction
            recon = DocumentReconstruction(
                document_id=uuid.UUID(document_id),
                normalized_text=normalized_text,
                page_offset_map=page_offset_map
            )
            self.db.add(recon)
            
            units_created = 0
            
            # Save units recursively
            def save_unit_recursive(data: LegalUnitData, parent_id: uuid.UUID = None) -> uuid.UUID:
                nonlocal units_created
                db_unit = LegalUnit(
                    document_id=uuid.UUID(document_id),
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
                    document_id=uuid.UUID(document_id),
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
                
            self.db.commit()
            return units_created, chunks_created
        except Exception:
            self.db.rollback()
            raise
