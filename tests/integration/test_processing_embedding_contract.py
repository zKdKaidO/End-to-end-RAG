import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import delete, func, select

from app.db.database import SessionLocal
from app.indexing.input_contract import EmbeddingInputContractViolation
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.indexing_job import IndexingJob
from app.models.document_page import DocumentPage
from app.models.document_processing_job import DocumentProcessingJob
from app.models.document_reconstruction import DocumentReconstruction
from app.models.legal_unit import LegalUnit
from app.processing_worker_main import process_document
from app.repositories.processing_job_repo import ProcessingJobRepository


def test_invalid_final_embedding_set_fails_atomically_in_chunking_stage():
    db = SessionLocal()
    document_id = uuid.uuid4()
    try:
        db.add(Document(
            id=document_id,
            filename="embedding-contract.pdf",
            mime_type="application/pdf",
            file_size=100,
            status="COMPLETED",
            sha256=str(document_id),
        ))
        db.add(DocumentPage(
            document_id=document_id,
            page_number=1,
            raw_text="Điều 1. Nội dung kiểm tra hợp đồng embedding.",
            char_count=45,
        ))
        db.commit()
        job = ProcessingJobRepository(db).create_job(str(document_id))
        job_id = job.id

        invalid_chunks = [{
            "chunk_index": 0,
            "content_text": "word " * 600,
            "embedding_text": "word " * 600,
            "char_start": 0,
            "char_end": 10,
        }]
        with patch("app.processing.chunker.Chunker.generate_chunks", return_value=invalid_chunks):
            with pytest.raises(EmbeddingInputContractViolation):
                process_document(str(job_id), str(document_id), "embedding-contract-test")

        db.expire_all()
        failed_job = db.get(DocumentProcessingJob, job_id)
        assert failed_job.status == "FAILED"
        assert failed_job.error_stage == "CHUNKING"
        assert failed_job.error_type == "EmbeddingInputContractViolation"
        assert db.scalar(select(func.count(DocumentReconstruction.id)).where(
            DocumentReconstruction.document_id == document_id
        )) == 0
        assert db.scalar(select(func.count(LegalUnit.id)).where(LegalUnit.document_id == document_id)) == 0
        assert db.scalar(select(func.count(Chunk.id)).where(Chunk.document_id == document_id)) == 0
        assert db.scalar(select(func.count(IndexingJob.id)).where(
            IndexingJob.document_id == document_id
        )) == 0
    finally:
        db.rollback()
        db.execute(delete(DocumentPage).where(DocumentPage.document_id == document_id))
        db.execute(delete(Document).where(Document.id == document_id))
        db.commit()
        db.close()
