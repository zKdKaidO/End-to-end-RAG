from collections.abc import Sequence
from uuid import UUID

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.indexing.constants import CANONICAL_INDEX_VERSION
from app.retrieval.types import DenseCandidate, HydratedChunk, LexicalCandidate


EMBEDDING_MODEL = "intfloat/multilingual-e5-base"
EMBEDDING_DIMENSION = 768
LEXICAL_FALLBACK_LEXEME_LIMIT = 4


class RetrievalRepository:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _document_filter(document_ids: Sequence[UUID]) -> str:
        if not document_ids:
            return ""
        return "AND ci.document_id = ANY(CAST(:document_ids AS uuid[]))"

    @staticmethod
    def _vector_literal(vector: np.ndarray) -> str:
        return "[" + ",".join(format(float(value), ".9g") for value in vector) + "]"

    def dense_search(
        self,
        query_vector: np.ndarray,
        top_k: int,
        document_ids: Sequence[UUID],
    ) -> list[DenseCandidate]:
        sql = f"""
            SELECT
                ci.chunk_id,
                ci.document_id,
                1 - (ci.embedding <=> CAST(:query_vector AS vector)) AS dense_score
            FROM chunk_indexes AS ci
            WHERE ci.embedding IS NOT NULL
              AND ci.embedding_model = :embedding_model
              AND ci.embedding_dimension = :embedding_dimension
              AND ci.index_version = :index_version
              {self._document_filter(document_ids)}
            ORDER BY ci.embedding <=> CAST(:query_vector AS vector) ASC
            LIMIT :top_k
        """
        params = {
            "query_vector": self._vector_literal(query_vector),
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dimension": EMBEDDING_DIMENSION,
            "index_version": CANONICAL_INDEX_VERSION,
            "top_k": top_k,
        }
        if document_ids:
            params["document_ids"] = [str(document_id) for document_id in document_ids]

        rows = self.db.execute(text(sql), params).mappings().all()
        return [
            DenseCandidate(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                dense_score=float(row["dense_score"]),
                dense_rank=rank,
            )
            for rank, row in enumerate(rows, start=1)
        ]

    def lexical_search(
        self,
        query_text: str,
        top_k: int,
        document_ids: Sequence[UUID],
    ) -> list[LexicalCandidate]:
        sql = f"""
            WITH strict_query AS (
                SELECT websearch_to_tsquery('simple', :query_text) AS value
            ),
            strict_available AS (
                SELECT EXISTS (
                    SELECT 1
                    FROM chunk_indexes AS ci
                    CROSS JOIN strict_query
                    WHERE ci.lexical_tsv @@ strict_query.value
                      AND ci.embedding_model = :embedding_model
                      AND ci.embedding_dimension = :embedding_dimension
                      AND ci.index_version = :index_version
                      {self._document_filter(document_ids)}
                ) AS value
            ),
            normalized_lexemes AS (
                SELECT DISTINCT
                    unnest(tsvector_to_array(to_tsvector('simple', :query_text))) AS lexeme
            ),
            lexeme_stats AS (
                SELECT nl.lexeme, count(ci.chunk_id) AS document_frequency
                FROM normalized_lexemes AS nl
                JOIN chunk_indexes AS ci
                  ON ci.lexical_tsv @@ to_tsquery('simple', quote_literal(nl.lexeme))
                 AND ci.embedding_model = :embedding_model
                 AND ci.embedding_dimension = :embedding_dimension
                 AND ci.index_version = :index_version
                 {self._document_filter(document_ids)}
                GROUP BY nl.lexeme
            ),
            selected_lexemes AS (
                SELECT lexeme
                FROM lexeme_stats
                WHERE document_frequency > 0
                ORDER BY document_frequency ASC, lexeme ASC
                LIMIT :fallback_lexeme_limit
            ),
            fallback_query AS (
                SELECT CASE
                    WHEN count(*) = 0 THEN NULL::tsquery
                    ELSE to_tsquery(
                        'simple',
                        string_agg(quote_literal(lexeme), ' & ' ORDER BY lexeme)
                    )
                END AS value
                FROM selected_lexemes
            ),
            lexical_query AS (
                SELECT CASE
                    WHEN strict_available.value THEN strict_query.value
                    ELSE fallback_query.value
                END AS value
                FROM strict_query, strict_available, fallback_query
            )
            SELECT
                ci.chunk_id,
                ci.document_id,
                ts_rank_cd(ci.lexical_tsv, lexical_query.value) AS lexical_score
            FROM chunk_indexes AS ci
            CROSS JOIN lexical_query
            WHERE ci.lexical_tsv @@ lexical_query.value
              AND ci.embedding_model = :embedding_model
              AND ci.embedding_dimension = :embedding_dimension
              AND ci.index_version = :index_version
              {self._document_filter(document_ids)}
            ORDER BY lexical_score DESC, ci.chunk_id ASC
            LIMIT :top_k
        """
        params = {
            "query_text": query_text,
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dimension": EMBEDDING_DIMENSION,
            "index_version": CANONICAL_INDEX_VERSION,
            "top_k": top_k,
            "fallback_lexeme_limit": LEXICAL_FALLBACK_LEXEME_LIMIT,
        }
        if document_ids:
            params["document_ids"] = [str(document_id) for document_id in document_ids]

        rows = self.db.execute(text(sql), params).mappings().all()
        return [
            LexicalCandidate(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                lexical_score=float(row["lexical_score"]),
                lexical_rank=rank,
            )
            for rank, row in enumerate(rows, start=1)
        ]

    def hydrate(self, chunk_ids: Sequence[UUID]) -> dict[UUID, HydratedChunk]:
        if not chunk_ids:
            return {}
        rows = self.db.execute(
            text(
                """
                SELECT id, document_id, content_text, metadata_json, provenance_json, legal_unit_id
                FROM chunks
                WHERE id = ANY(CAST(:chunk_ids AS uuid[]))
                """
            ),
            {"chunk_ids": [str(chunk_id) for chunk_id in chunk_ids]},
        ).mappings().all()
        return {
            row["id"]: HydratedChunk(
                chunk_id=row["id"],
                document_id=row["document_id"],
                content_text=row["content_text"],
                metadata_json=row["metadata_json"],
                provenance_json=row["provenance_json"],
                legal_unit_id=row.get("legal_unit_id"),
            )
            for row in rows
        }
