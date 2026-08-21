import time
import uuid
import pytest
from app.db.database import SessionLocal
from app.repositories.document_repo import DocumentRepository
from app.repositories.processing_job_repo import ProcessingJobRepository
from app.queue.rq_client import rq_client

def test_document_processing_queue():
    db = SessionLocal()
    doc_repo = DocumentRepository(db)
    repo = ProcessingJobRepository(db)
    
    # 1. Create mock document
    doc = doc_repo.create("mock.pdf", "application/pdf", 100, f"hash_{uuid.uuid4()}")
    doc_id = str(doc.id)
    
    # 2. Create processing job
    p_job = repo.create_job(doc_id)
    assert p_job.status == "PENDING"
    job_id = str(p_job.id)
    
    # 3. Enqueue job
    rq_client.enqueue_document_processing_job(job_id, doc_id)
    
    # 4. Wait for worker to consume
    time.sleep(2)
    
    db.refresh(p_job)
    assert p_job.status in ["PROCESSING", "COMPLETED", "FAILED"]
    # Currently process_document is a stub that marks COMPLETED
    print(f"Status is {p_job.status}")
    db.close()
