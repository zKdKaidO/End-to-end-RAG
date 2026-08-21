import pytest
import uuid
import numpy as np
from sqlalchemy import text
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.chunk_index import ChunkIndex
from app.repositories.chunk_index_repo import ChunkIndexRepository
from app.db.database import SessionLocal
from sqlalchemy import func
from app.indexing.constants import CANONICAL_INDEX_VERSION

@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()

def test_upsert_lexical_tsv(db):
    repo = ChunkIndexRepository(db)
    
    # 1. Create a document
    doc = Document(
        filename="test.pdf",
        mime_type="application/pdf",
        file_size=1024,
        sha256=str(uuid.uuid4().hex),
        status="COMPLETED"
    )
    db.add(doc)
    db.flush()
    
    # 2. Create a chunk
    chunk = Chunk(
        document_id=doc.id,
        chunk_index=1,
        content_text="This is an artificial test text for lexical searching with pgvector and postgres.",
        embedding_text="passage: This is an artificial test text for lexical searching with pgvector and postgres.",
        page_start=1,
        page_end=1
    )
    db.add(chunk)
    db.flush()
    
    # 3. Create index data
    emb = np.random.rand(768).astype(np.float32)
    
    index_data = [{
        "chunk_id": chunk.id,
        "document_id": doc.id,
        "embedding": emb,
        "lexical_tsv": func.to_tsvector('simple', chunk.content_text),
        "embedding_model": "test-model",
        "embedding_dimension": 768,
        "index_version": CANONICAL_INDEX_VERSION
    }]
    
    # 4. Upsert
    repo.upsert_indexes(doc.id, index_data)
    
    # 5. Verify TSVECTOR
    res = db.execute(
        text("SELECT lexical_tsv, embedding FROM chunk_indexes WHERE chunk_id = :cid"),
        {"cid": chunk.id}
    ).fetchone()
    
    assert res is not None
    tsv_str = str(res[0])
    
    assert "artificial" in tsv_str
    assert "postgres" in tsv_str
    assert "lexical" in tsv_str
    
    emb_returned = res[1]
    if isinstance(emb_returned, str):
        import json
        emb_returned = json.loads(emb_returned)
    assert len(emb_returned) == 768
    assert np.allclose(emb_returned, emb, atol=1e-5)
from sqlalchemy import text
def test_vector_norm():
    db_session = SessionLocal()
    res = db_session.execute(text("SELECT vector_norm('[3, 4, 0]'::vector)")).scalar()
    assert float(res) == 5.0

