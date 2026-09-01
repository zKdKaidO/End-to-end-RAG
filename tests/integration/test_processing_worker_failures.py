import pytest
import uuid
from unittest.mock import patch
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.repositories.processing_job_repo import ProcessingJobRepository
from app.processing_worker_main import process_document

pytestmark = pytest.mark.isolated_document_corpus

def test_deterministic_failure_classification():
    # Setup job
    db = SessionLocal()
    repo = ProcessingJobRepository(db)
    doc_id = uuid.uuid4()
    from app.models.document import Document
    doc = Document(id=doc_id, filename='fake.pdf', mime_type='application/pdf', file_size=123, status='COMPLETED', sha256=str(doc_id))
    db.add(doc)
    db.commit()
    
    job = repo.create_job(str(doc_id))
    job_id = str(job.id)
    
    # Mock the parser to raise ValueError
    with patch('app.processing.parser.LegalParser.parse', side_effect=ValueError("Test parser failure")):
        with pytest.raises(ValueError):
            process_document(job_id, str(doc_id))
            
    # Check DB status
    db.expunge_all()
    db_job = repo.get_by_id(job_id)
    assert db_job.status == "FAILED"
    assert db_job.error_stage == "LEGAL_PARSING"
    assert db_job.error_type == "ValueError"
    assert "Test parser failure" in db_job.error_message
    db.close()
