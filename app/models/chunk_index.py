import uuid
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from app.db.base import Base

class ChunkIndex(Base):
    __tablename__ = "chunk_indexes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False, unique=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)

    embedding = Column(Vector(768), nullable=True)
    lexical_tsv = Column(TSVECTOR, nullable=True)

    embedding_model = Column(String, nullable=False)
    embedding_dimension = Column(Integer, nullable=False, default=768)
    index_version = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    chunk = relationship("Chunk")
    document = relationship("Document")

    __table_args__ = (
        Index('ix_chunk_indexes_embedding', 'embedding', postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'}),
        Index('ix_chunk_indexes_lexical_tsv', 'lexical_tsv', postgresql_using='gin'),
        Index('ix_chunk_indexes_document_id', 'document_id'),
    )
