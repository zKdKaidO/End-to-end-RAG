import pytest
from sqlalchemy.orm import Session
from sqlalchemy import text
import uuid
import time
import numpy as np
from app.db.database import SessionLocal
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.chunk_index import ChunkIndex
from app.models.indexing_job import IndexingJob
from app.indexing_worker_main import process_indexing
from app.repositories.indexing_job_repo import IndexingJobRepository
from app.indexing.constants import CANONICAL_INDEX_VERSION

def setup_data(db: Session):
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        filename="idempotency.pdf",
        mime_type="application/pdf",
        file_size=1024,
        sha256=doc_id,
        status="COMPLETED"
    )
    db.add(doc)
    
    chunks = []
    for i in range(3):
        chunk = Chunk(
            document_id=doc_id,
            chunk_index=i,
            content_text=f"This is chunk {i} for idempotency testing.",
            embedding_text=f"passage: This is chunk {i} for idempotency testing.",
            page_start=1,
            page_end=1
        )
        db.add(chunk)
        chunks.append(chunk)
        
    db.commit()
    return doc_id, [c.id for c in chunks]

def test_idempotency():
    db = SessionLocal()
    doc_id, chunk_ids = setup_data(db)
    
    repo = IndexingJobRepository(db)
    
    # 1. First run
    job1 = repo.create_job(doc_id, index_version=CANONICAL_INDEX_VERSION, embedding_model="intfloat/multilingual-e5-base")
    process_indexing(doc_id, str(job1.id), "req1")
    
    # Verify first run
    db.expunge_all()
    job1_db = repo.get_by_id(str(job1.id))
    assert job1_db.status == "COMPLETED"
    assert job1_db.chunks_indexed == 3
    assert job1_db.index_version == CANONICAL_INDEX_VERSION
    
    indexes1 = db.query(ChunkIndex).filter(ChunkIndex.document_id == doc_id).all()
    assert len(indexes1) == 3
    assert {index.index_version for index in indexes1} == {CANONICAL_INDEX_VERSION}
    index1_ids = sorted([str(i.id) for i in indexes1])
    
    # 2. Second run (reindex)
    job2 = repo.create_job(doc_id, index_version=CANONICAL_INDEX_VERSION, embedding_model="intfloat/multilingual-e5-base")
    process_indexing(doc_id, str(job2.id), "req2")
    
    # Verify second run
    db.expunge_all()
    job2_db = repo.get_by_id(str(job2.id))
    assert job2_db.status == "COMPLETED"
    assert job2_db.chunks_indexed == 3
    assert job2_db.index_version == CANONICAL_INDEX_VERSION
    
    indexes2 = db.query(ChunkIndex).filter(ChunkIndex.document_id == doc_id).all()
    assert len(indexes2) == 3 # No duplicates!
    assert {index.index_version for index in indexes2} == {CANONICAL_INDEX_VERSION}
    index2_ids = sorted([str(i.id) for i in indexes2])
    
    assert index1_ids == index2_ids # Same row IDs because of UPSERT matching on chunk_id!
    
    # 3. Test CASCADE delete
    db.execute(text("DELETE FROM chunks WHERE id = :cid"), {"cid": chunk_ids[0]})
    db.commit()
    
    indexes3 = db.query(ChunkIndex).filter(ChunkIndex.document_id == doc_id).all()
    assert len(indexes3) == 2 # Cascade worked!
    
    db.close()
