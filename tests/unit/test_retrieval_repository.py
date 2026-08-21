from uuid import UUID

import numpy as np

from app.indexing.constants import CANONICAL_INDEX_VERSION
from app.retrieval.hierarchy_repository import HierarchyRepository
from app.retrieval.repository import LEXICAL_FALLBACK_LEXEME_LIMIT, RetrievalRepository


CHUNK_A = UUID("00000000-0000-0000-0000-000000000001")
CHUNK_B = UUID("00000000-0000-0000-0000-000000000002")
DOC_A = UUID("00000000-0000-0000-0000-000000000010")


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


class RecordingSession:
    def __init__(self, batches):
        self.batches = list(batches)
        self.calls = []

    def execute(self, statement, params):
        self.calls.append((str(statement), params))
        return FakeResult(self.batches.pop(0))


def test_dense_shape_order_rank_top_k_and_frozen_filters():
    db = RecordingSession(
        [[
            {"chunk_id": CHUNK_A, "document_id": DOC_A, "dense_score": 0.9},
            {"chunk_id": CHUNK_B, "document_id": DOC_A, "dense_score": 0.8},
        ]]
    )
    repo = RetrievalRepository(db)
    result = repo.dense_search(np.eye(1, 768, dtype=np.float32)[0], 2, [])
    sql, params = db.calls[0]

    assert [item.dense_rank for item in result] == [1, 2]
    assert [item.dense_score for item in result] == [0.9, 0.8]
    assert "ORDER BY ci.embedding <=> CAST(:query_vector AS vector) ASC" in sql
    assert "ASC, ci.chunk_id" not in sql
    assert params["top_k"] == 2
    assert params["embedding_model"] == "intfloat/multilingual-e5-base"
    assert params["embedding_dimension"] == 768
    assert params["index_version"] == CANONICAL_INDEX_VERSION
    assert "hnsw.iterative_scan" not in sql


def test_hierarchy_lookup_is_one_parameterized_direct_child_query():
    db = RecordingSession([[]])
    result = HierarchyRepository(db).lookup_direct_children([CHUNK_A, CHUNK_B], [DOC_A])
    assert result == []
    assert len(db.calls) == 1
    sql, params = db.calls[0]
    assert "child.parent_unit_id = anchors.legal_unit_id" in sql
    assert "JOIN legal_units AS child" in sql
    assert "JOIN chunks AS child_chunk" in sql
    assert "child_chunk.document_id = ANY(CAST(:document_ids AS uuid[]))" in sql
    assert "ORDER BY\n                    anchors.anchor_order" in sql
    assert "child.char_start" in sql
    assert "child_chunk.chunk_index" in sql
    assert "WITH RECURSIVE" not in sql
    assert params["anchor_chunk_ids"] == [str(CHUNK_A), str(CHUNK_B)]
    assert params["document_ids"] == [str(DOC_A)]


def test_dense_document_filter_is_inside_sql_not_python():
    db = RecordingSession([[]])
    repo = RetrievalRepository(db)
    repo.dense_search(np.eye(1, 768, dtype=np.float32)[0], 5, [DOC_A])
    sql, params = db.calls[0]
    assert "ci.document_id = ANY(CAST(:document_ids AS uuid[]))" in sql
    assert params["document_ids"] == [str(DOC_A)]


def test_lexical_shape_rank_top_k_and_zero_match():
    db = RecordingSession(
        [[{"chunk_id": CHUNK_A, "document_id": DOC_A, "lexical_score": 0.4}], []]
    )
    repo = RetrievalRepository(db)
    result = repo.lexical_search("ưu đãi", 1, [])
    empty = repo.lexical_search("term-with-no-match", 3, [])
    sql, params = db.calls[0]

    assert result[0].lexical_rank == 1
    assert result[0].lexical_score == 0.4
    assert empty == []
    assert "websearch_to_tsquery('simple', :query_text)" in sql
    assert "to_tsvector('simple', :query_text)" in sql
    assert "quote_literal(nl.lexeme)" in sql
    assert "string_agg(quote_literal(lexeme), ' & '" in sql
    assert "SELECT DISTINCT" in sql
    assert "replace(" not in sql.lower()
    assert "ci.lexical_tsv @@ lexical_query.value" in sql
    assert params["top_k"] == 1
    assert params["fallback_lexeme_limit"] == LEXICAL_FALLBACK_LEXEME_LIMIT == 4
    assert params["query_text"] == "ưu đãi"


def test_lexical_document_filter_is_inside_sql_not_python():
    db = RecordingSession([[]])
    RetrievalRepository(db).lexical_search("ưu đãi", 5, [DOC_A])
    sql, params = db.calls[0]
    assert "ci.document_id = ANY(CAST(:document_ids AS uuid[]))" in sql
    assert params["document_ids"] == [str(DOC_A)]
    assert sql.count("ci.document_id = ANY(CAST(:document_ids AS uuid[]))") >= 3


def test_hydration_is_one_bulk_query_and_returns_all_fields():
    db = RecordingSession(
        [[
            {
                "id": CHUNK_B,
                "document_id": DOC_A,
                "content_text": "content b",
                "metadata_json": {"kind": "law"},
                "provenance_json": {"page": 2},
            },
            {
                "id": CHUNK_A,
                "document_id": DOC_A,
                "content_text": "content a",
                "metadata_json": {"kind": "law"},
                "provenance_json": {"page": 1},
            },
        ]]
    )
    hydrated = RetrievalRepository(db).hydrate([CHUNK_A, CHUNK_B])
    sql, params = db.calls[0]

    assert len(db.calls) == 1
    assert "WHERE id = ANY(CAST(:chunk_ids AS uuid[]))" in sql
    assert params["chunk_ids"] == [str(CHUNK_A), str(CHUNK_B)]
    assert hydrated[CHUNK_A].content_text == "content a"
    assert hydrated[CHUNK_A].metadata_json == {"kind": "law"}
    assert hydrated[CHUNK_A].provenance_json == {"page": 1}
