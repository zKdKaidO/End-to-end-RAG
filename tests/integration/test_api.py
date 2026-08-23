import pytest
import io
import os
import hashlib
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app
from app.db.database import SessionLocal
from app.models.document import Document
from app.models.ingestion_job import IngestionJob

client = TestClient(app)

def get_fixture_path():
    return os.path.join(os.path.dirname(__file__), "..", "fixtures", "sample_legal.pdf")

def read_fixture():
    with open(get_fixture_path(), "rb") as f:
        return f.read()

def test_invalid_pdf_format():
    response = client.post(
        "/documents",
        files={"file": ("test.txt", io.BytesIO(b"Hello World"), "text/plain")}
    )
    assert response.status_code == 400
    assert "Invalid PDF format" in response.json()["detail"]

def test_oversized_pdf():
    # max upload size is 10MB in config
    oversized = b"%PDF-1.4\n" + b"A" * (10 * 1024 * 1024 + 10)
    response = client.post(
        "/documents",
        files={"file": ("oversized.pdf", io.BytesIO(oversized), "application/pdf")}
    )
    assert response.status_code == 413
    assert "UPLOAD_TOO_LARGE" in response.text or "REQUEST_TOO_LARGE" in response.text

def test_real_pdf_upload():
    file_bytes = read_fixture()
    sha256 = hashlib.sha256(file_bytes).hexdigest()
    
    response = client.post(
        "/documents",
        files={"file": ("sample_legal.pdf", io.BytesIO(file_bytes), "application/pdf")}
    )
    assert response.status_code == 202
    data = response.json()["document"]
    
    doc_id = data["id"]
    assert data["status"] in ["PENDING", "PROCESSING", "COMPLETED"]
    assert data["sha256"] == sha256
    
    # DB verify
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        assert doc is not None
        assert doc.sha256 == sha256
        assert doc.status.value in ["PENDING", "PROCESSING", "COMPLETED"]
        
        job = db.query(IngestionJob).filter(IngestionJob.document_id == doc_id).first()
        assert job is not None
        assert job.status in ["PENDING", "PROCESSING", "COMPLETED"]
        
        # In Minio, check object exists
        from app.storage.minio_client import minio_client
        assert minio_client.exists(str(doc_id))
        
        # Verify content
        downloaded = minio_client.download_pdf(str(doc_id))
        assert downloaded == file_bytes
        
    finally:
        db.close()
        
    return doc_id

def test_deduplication():
    doc_id = test_real_pdf_upload()
    
    file_bytes = read_fixture()
    
    db = SessionLocal()
    initial_doc_count = db.query(Document).count()
    initial_job_count = db.query(IngestionJob).count()
    db.close()
    
    response = client.post(
        "/documents",
        files={"file": ("sample_legal.pdf", io.BytesIO(file_bytes), "application/pdf")}
    )
    assert response.status_code == 202
    data = response.json()["document"]
    assert data["id"] == str(doc_id)
    
    db = SessionLocal()
    new_doc_count = db.query(Document).count()
    new_job_count = db.query(IngestionJob).count()
    db.close()
    
    assert initial_doc_count == new_doc_count
    assert initial_job_count == new_job_count

def test_minio_unavailable_on_upload():
    import uuid
    file_bytes = read_fixture() + f"\n%{uuid.uuid4()}".encode()
    with patch("app.services.upload_service.MinioClient.upload_pdf", side_effect=Exception("Storage offline")):
        response = client.post(
            "/documents",
            files={"file": ("mocked.pdf", io.BytesIO(file_bytes), "application/pdf")}
        )
        assert response.status_code == 500
        
    sha256 = hashlib.sha256(file_bytes).hexdigest()
    db = SessionLocal()
    doc = db.query(Document).filter(Document.sha256 == sha256).first()
    # Ensure document was marked FAILED
    assert doc.status.value == "FAILED"
    
    # Job should not be created since we failed at step 4
    job = db.query(IngestionJob).filter(IngestionJob.document_id == doc.id).first()
    assert job is None
    db.close()

def test_queue_unavailable_on_upload():
    import uuid
    file_bytes = read_fixture() + f"\n%{uuid.uuid4()}".encode()
    with patch("app.services.upload_service.RQClient.enqueue_ingestion_job", side_effect=Exception("Queue offline")):
        response = client.post(
            "/documents",
            files={"file": ("mocked2.pdf", io.BytesIO(file_bytes), "application/pdf")}
        )
        assert response.status_code == 500
        
    sha256 = hashlib.sha256(file_bytes).hexdigest()
    db = SessionLocal()
    doc = db.query(Document).filter(Document.sha256 == sha256).first()
    assert doc.status.value == "FAILED"
    
    job = db.query(IngestionJob).filter(IngestionJob.document_id == doc.id).first()
    assert job is not None
    assert job.status == "FAILED"
    assert job.error_stage == "QUEUE"
    db.close()

def test_state_regression_protection():
    # Create job directly
    db = SessionLocal()
    from app.repositories.document_repo import DocumentRepository
    from app.repositories.job_repo import JobRepository
    doc_repo = DocumentRepository(db)
    job_repo = JobRepository(db)
    
    import uuid
    fake_hash = "fakehash123_" + str(uuid.uuid4())
    doc = doc_repo.create("regression.pdf", "application/pdf", 100, fake_hash)
    job = job_repo.create_job(str(doc.id))
    
    # Change status to PROCESSING simulating worker picking it up
    job.status = "PROCESSING"
    doc.status = "PROCESSING"
    db.commit()
    
    # Now try to transition to PENDING
    success = job_repo.transition_to_pending(str(job.id))
    assert success is False
    
    db.refresh(job)
    assert job.status == "PROCESSING"
    db.close()
from unittest.mock import patch
from redis.exceptions import ConnectionError
from fastapi.testclient import TestClient
from app.main import app
from redis.exceptions import ConnectionError
import uuid
from app.models.document import Document

def test_queue_failure_on_index_upload():
    from app.models.auth import GlobalDocumentAccess

    db_session = SessionLocal()
    client = TestClient(app)
    doc_id = str(uuid.uuid4())
    doc = Document(id=doc_id, filename='fake.pdf', mime_type='application/pdf', file_size=123, status='COMPLETED', sha256=doc_id)
    db_session.add(doc)
    db_session.commit()
    db_session.add(GlobalDocumentAccess(
        document_id=doc.id,
        granted_by_user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    ))
    db_session.commit()

    with patch('rq.Queue.enqueue') as mock_enqueue:
        mock_enqueue.side_effect = ConnectionError("Redis is down")
        
        response = client.post(f"/documents/{doc_id}/index")
        assert response.status_code == 500
        
        # Verify job is failed and error_stage is QUEUE
        res = client.get(f"/documents/{doc_id}/indexing-status")
        assert res.status_code == 200
        assert res.json()['status'] == 'FAILED'
        
        job_id = res.json()['job_id']
        job_res = client.get(f"/indexing-jobs/{job_id}")
        assert job_res.json()['error_stage'] == 'QUEUE'

