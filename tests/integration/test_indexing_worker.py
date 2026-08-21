import pytest
import uuid
from unittest.mock import patch, MagicMock
from app.models.document import Document
from app.models.chunk import Chunk
from app.repositories.indexing_job_repo import IndexingJobRepository
from app.indexing_worker_main import process_indexing
from app.db.database import SessionLocal
from app.indexing.constants import CANONICAL_INDEX_VERSION
from app.models.chunk_index import ChunkIndex

@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()

def test_indexing_worker_success(db):
    doc = Document(
        filename="test_idx.pdf",
        mime_type="application/pdf",
        file_size=1024,
        sha256=str(uuid.uuid4().hex),
        status="COMPLETED"
    )
    db.add(doc)
    db.flush()
    
    # Add chunks
    chunk1 = Chunk(document_id=doc.id, chunk_index=1, content_text="Chunk 1", embedding_text="Chunk 1", page_start=1, page_end=1)
    chunk2 = Chunk(document_id=doc.id, chunk_index=2, content_text="Chunk 2", embedding_text="Chunk 2", page_start=1, page_end=1)
    db.add_all([chunk1, chunk2])
    db.flush()

    repo = IndexingJobRepository(db)
    job = repo.create_job(doc.id, CANONICAL_INDEX_VERSION, "test-model")
    job_id = job.id
    
    with patch('app.indexing_worker_main.E5Embedder.get_instance') as mock_get_embedder:
        mock_embedder = MagicMock()
        mock_embedder.model_name = "test-model"
        mock_embedder.embedding_dimension = 768
        mock_embedder.encode_batch.return_value = [[0.1]*768, [0.2]*768]
        mock_get_embedder.return_value = mock_embedder
        
        process_indexing(doc.id, job_id, "req-123")
        
    db.expire_all()
    job = repo.get_by_id(job_id)
    assert job.status == "COMPLETED"
    assert job.current_stage == "FINALIZE"
    assert job.chunks_total == 2
    assert job.chunks_indexed == 2
    assert job.finished_at is not None
    indexes = db.query(ChunkIndex).filter(ChunkIndex.document_id == doc.id).all()
    assert {index.index_version for index in indexes} == {CANONICAL_INDEX_VERSION}

def test_indexing_worker_failure(db):
    doc = Document(
        filename="fail.pdf",
        mime_type="application/pdf",
        file_size=1024,
        sha256=str(uuid.uuid4().hex),
        status="COMPLETED"
    )
    db.add(doc)
    db.flush()
    
    # 0 chunks -> ValueError("No chunks found")
    
    repo = IndexingJobRepository(db)
    job = repo.create_job(doc.id, CANONICAL_INDEX_VERSION, "test-model")
    job_id = job.id
    
    with patch('app.indexing_worker_main.get_current_job') as mock_get_rq:
        mock_rq = MagicMock()
        mock_get_rq.return_value = mock_rq
        
        with pytest.raises(ValueError):
            process_indexing(doc.id, job_id, "req-fail")
            
    db.expire_all()
    job = repo.get_by_id(job_id)
    assert job.status == "FAILED"
    assert job.error_stage == "LOAD_CHUNKS"
    assert job.error_type == "ValueError"
    assert "No chunks found" in job.error_message
