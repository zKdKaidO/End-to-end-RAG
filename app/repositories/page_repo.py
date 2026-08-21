from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select
from app.models.document_page import DocumentPage
from app.models.ingestion_job import IngestionJob

class PageRepository:
    def __init__(self, db: Session):
        self.db = db

    def batch_upsert_pages(self, document_id: str, job_id: str, pages_data: List[Dict]):
        """
        Upsert a batch of pages atomically and update the job's pages_processed.
        pages_data format: [{"page_number": 1, "raw_text": "...", "char_count": ...}, ...]
        """
        if not pages_data:
            return

        stmt = insert(DocumentPage).values([
            {
                "document_id": document_id,
                "page_number": p["page_number"],
                "raw_text": p["raw_text"],
                "char_count": p["char_count"]
            }
            for p in pages_data
        ])

        # Handle conflict by updating the existing text/char_count to ensure idempotency
        stmt = stmt.on_conflict_do_update(
            index_elements=['document_id', 'page_number'],
            set_={
                'raw_text': stmt.excluded.raw_text,
                'char_count': stmt.excluded.char_count
            }
        )

        self.db.execute(stmt)

        # Update job progress
        job = self.db.execute(select(IngestionJob).where(IngestionJob.id == job_id)).scalar_one_or_none()
        if job:
            # Re-calculate total processed pages or just increment depending on logic.
            # A safer idempotent way is to query the count of pages for the document.
            from sqlalchemy import func
            count = self.db.execute(
                select(func.count()).select_from(DocumentPage).where(DocumentPage.document_id == document_id)
            ).scalar()
            job.pages_processed = count

        self.db.commit()
