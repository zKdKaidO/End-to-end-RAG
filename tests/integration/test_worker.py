import pytest
from unittest.mock import patch
from collections import namedtuple

from app.worker_main import process_ingestion
from app.db.database import SessionLocal
from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.repositories.document_repo import DocumentRepository
from app.repositories.job_repo import JobRepository

def test_process_ingestion_success():
    db = SessionLocal()
    doc_repo = DocumentRepository(db)
    job_repo = JobRepository(db)
    
    import uuid
    fake_hash = "fake_hash_worker_1_" + str(uuid.uuid4())
    doc = doc_repo.create("worker_test.pdf", "application/pdf", 100, fake_hash)
    job = job_repo.create_job(str(doc.id))
    doc_id = str(doc.id)
    job_id = str(job.id)
    db.close()
    
    import os
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "sample_legal.pdf")
    with open(fixture_path, "rb") as f:
        real_pdf_bytes = f.read()

    with patch("app.worker_main.minio_client.download_pdf", return_value=real_pdf_bytes):
        process_ingestion(job_id, doc_id)
        
    db = SessionLocal()
    doc_after = db.query(Document).filter(Document.id == doc_id).first()
    job_after = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    
    assert doc_after.status.value == "COMPLETED"
    assert job_after.status == "COMPLETED"
    assert job_after.current_stage == "DONE"
    assert job_after.pages_total == 8
    assert job_after.pages_processed == 8
    
    from app.models.document_page import DocumentPage
    pages = db.query(DocumentPage).filter(DocumentPage.document_id == doc_id).order_by(DocumentPage.page_number).all()
    assert len(pages) == 8
    assert "CHÍNH PHỦ" in pages[0].raw_text
    db.close()
    
    # Test idempotency
    with patch("app.worker_main.minio_client.download_pdf", return_value=real_pdf_bytes):
        process_ingestion(job_id, doc_id)
        
    db = SessionLocal()
    pages_after = db.query(DocumentPage).filter(DocumentPage.document_id == doc_id).all()
    assert len(pages_after) == 8
    db.close()

def test_process_ingestion_terminal_failure():
    db = SessionLocal()
    doc_repo = DocumentRepository(db)
    job_repo = JobRepository(db)
    
    import uuid
    fake_hash = "fake_hash_worker_fail_" + str(uuid.uuid4())
    doc = doc_repo.create("worker_test_fail.pdf", "application/pdf", 100, fake_hash)
    job = job_repo.create_job(str(doc.id))
    doc_id = str(doc.id)
    job_id = str(job.id)
    db.close()
    
    MockJob = namedtuple("MockJob", ["retries_left"])
    
    with patch("app.worker_main.minio_client.download_pdf", side_effect=Exception("S3 Error")), \
         patch("app.worker_main.get_current_job", return_value=MockJob(retries_left=0)):
        
        with pytest.raises(Exception):
            process_ingestion(job_id, doc_id)
            
    db = SessionLocal()
    job_after = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    
    assert job_after.status == "FAILED"
    assert job_after.error_stage == "DOWNLOAD"
    assert job_after.error_message == "S3 Error"
    db.close()

def test_process_ingestion_transient_failure():
    db = SessionLocal()
    doc_repo = DocumentRepository(db)
    job_repo = JobRepository(db)
    
    import uuid
    fake_hash = "fake_hash_worker_transient_" + str(uuid.uuid4())
    doc = doc_repo.create("worker_test_transient.pdf", "application/pdf", 100, fake_hash)
    job = job_repo.create_job(str(doc.id))
    doc_id = str(doc.id)
    job_id = str(job.id)
    db.close()
    
    MockJob = namedtuple("MockJob", ["retries_left"])
    
    # retries_left > 0 means it's transient
    with patch("app.worker_main.minio_client.download_pdf", side_effect=Exception("Network glitch")), \
         patch("app.worker_main.get_current_job", return_value=MockJob(retries_left=1)):
        
        with pytest.raises(Exception):
            process_ingestion(job_id, doc_id)
            
    db = SessionLocal()
    job_after = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    
    # The application status should NOT be FAILED yet because retries remain
    assert job_after.status != "FAILED"
    assert job_after.current_stage == "DOWNLOAD"
    db.close()
