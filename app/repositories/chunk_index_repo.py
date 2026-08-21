from sqlalchemy.orm import Session
from sqlalchemy import select, delete, func
from sqlalchemy.dialects.postgresql import insert
import numpy as np
from app.models.chunk_index import ChunkIndex
from app.models.chunk import Chunk

class ChunkIndexRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_chunks_for_document(self, document_id: str) -> list[Chunk]:
        return self.db.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index.asc())
        ).scalars().all()

    def upsert_indexes(self, document_id: str, index_data: list[dict]):
        if not index_data:
            return

        # Prepare values for upsert
        stmt = insert(ChunkIndex).values(index_data)

        # On conflict (chunk_id is UNIQUE), update the fields
        stmt = stmt.on_conflict_do_update(
            index_elements=['chunk_id'],
            set_=dict(
                embedding=stmt.excluded.embedding,
                lexical_tsv=stmt.excluded.lexical_tsv,
                embedding_model=stmt.excluded.embedding_model,
                embedding_dimension=stmt.excluded.embedding_dimension,
                index_version=stmt.excluded.index_version,
                updated_at=func.now()
            )
        )

        self.db.execute(stmt)
        self.db.commit()
        
    def count_indexed_chunks(self, document_id: str, index_version: str) -> int:
        return self.db.execute(
            select(func.count(ChunkIndex.id))
            .where(
                ChunkIndex.document_id == document_id,
                ChunkIndex.index_version == index_version
            )
        ).scalar()

    def validate_index_output(self, document_id: str, index_version: str, embedding_model: str, expected_total: int) -> None:
        indexes = self.db.execute(
            select(ChunkIndex)
            .where(ChunkIndex.document_id == document_id, ChunkIndex.index_version == index_version)
        ).scalars().all()
        
        if len(indexes) != expected_total:
            raise ValueError(f"Indexed chunks ({len(indexes)}) does not match total chunks ({expected_total})")
            
        for idx in indexes:
            if idx.embedding is None:
                raise ValueError(f"Null embedding for chunk {idx.chunk_id}")
            if idx.lexical_tsv is None:
                raise ValueError(f"Null lexical_tsv for chunk {idx.chunk_id}")
            if idx.embedding_model != embedding_model:
                raise ValueError(f"Wrong embedding_model {idx.embedding_model} for chunk {idx.chunk_id}")
            if idx.index_version != index_version:
                raise ValueError(f"Wrong index_version {idx.index_version} for chunk {idx.chunk_id}")
            # Note: dimension and finiteness are checked before insertion or by PG constraint
