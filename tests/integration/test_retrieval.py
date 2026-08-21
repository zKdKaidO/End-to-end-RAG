from uuid import UUID, uuid4

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.routes.retrieval import get_retrieval_service
from app.db.database import SessionLocal
from app.main import app
from app.retrieval.exceptions import QueryInputTooLongError, RetrievalDependencyError, RetrievalError
from app.retrieval.query_embedder import QueryEmbedder
from app.retrieval.repository import RetrievalRepository
from app.retrieval.rrf import reciprocal_rank_fusion
from app.retrieval.schemas import RetrievalRequest
from app.retrieval.service import RetrievalService, validate_request


client = TestClient(app)


class CapturingService:
    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error
        self.params = None

    def retrieve(self, params):
        self.params = params
        if self.error:
            raise self.error
        return self.results


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def override(service):
    app.dependency_overrides[get_retrieval_service] = lambda: service


def test_api_valid_defaults_and_custom_top_k():
    service = CapturingService()
    override(service)
    response = client.post("/retrieve", json={"query_text": "legal query"})
    assert response.status_code == 200
    assert response.json() == {"results": []}
    assert service.params.top_k_dense == 50
    assert service.params.top_k_lexical == 50
    assert service.params.top_k_final == 10
    assert service.params.rrf_k == 60

    response = client.post(
        "/retrieve",
        json={
            "query_text": "legal query",
            "top_k_dense": 7,
            "top_k_lexical": 8,
            "top_k_final": 3,
            "rrf_k": 42,
        },
    )
    assert response.status_code == 200
    assert service.params.top_k_dense == 7
    assert service.params.top_k_lexical == 8
    assert service.params.top_k_final == 3
    assert service.params.rrf_k == 42


def test_api_output_contract_has_raw_signals_and_no_pagination_or_normalized_score():
    result = {
        "chunk_id": str(uuid4()),
        "document_id": str(uuid4()),
        "content_text": "evidence",
        "metadata_json": {"kind": "law"},
        "provenance_json": {"page": 1},
        "dense_score": None,
        "dense_rank": None,
        "lexical_score": 0.2,
        "lexical_rank": 1,
        "fusion_score": 1 / 61,
        "final_rank": 1,
    }
    override(CapturingService(results=[result]))
    response = client.post("/retrieve", json={"query_text": "legal query"})
    assert response.status_code == 200
    emitted = response.json()["results"][0]
    assert {key: emitted[key] for key in result} == result
    assert emitted["retrieval_final_rank"] == 1
    assert emitted["context_candidate_order"] == 1
    assert emitted["candidate_origin"] == "RETRIEVAL"
    assert emitted["hierarchy_relation"] is None
    assert emitted["hierarchy_depth"] == 0
    assert emitted["hierarchy_anchor_references"] == []
    assert "normalized_score" not in response.text
    assert "confidence" not in response.text

    for forbidden_field in ("offset", "page", "cursor"):
        response = client.post(
            "/retrieve", json={"query_text": "legal query", forbidden_field: 1}
        )
        assert response.status_code == 400


@pytest.mark.parametrize("query", ["", "   "])
def test_api_empty_query_is_400(query):
    override(CapturingService())
    response = client.post("/retrieve", json={"query_text": query})
    assert response.status_code == 400
    assert response.json()["detail"]["stage"] == "VALIDATE_QUERY"


@pytest.mark.parametrize(
    "field,value",
    [
        ("top_k_dense", 0),
        ("top_k_lexical", -1),
        ("top_k_final", 0),
        ("rrf_k", 0),
        ("top_k_dense", 201),
    ],
)
def test_api_invalid_top_k_is_400(field, value):
    override(CapturingService())
    payload = {"query_text": "legal query", field: value}
    assert client.post("/retrieve", json=payload).status_code == 400


def test_api_invalid_document_uuid_is_400_and_ids_are_deduplicated():
    service = CapturingService()
    override(service)
    assert client.post(
        "/retrieve", json={"query_text": "legal", "document_ids": ["bad"]}
    ).status_code == 400

    document_id = str(uuid4())
    response = client.post(
        "/retrieve",
        json={"query_text": "legal", "document_ids": [document_id, document_id]},
    )
    assert response.status_code == 200
    assert service.params.document_ids == (UUID(document_id),)


def test_api_query_too_long_dependency_and_internal_errors():
    cases = [
        (QueryInputTooLongError(513, 512), 400, "QUERY_EMBEDDING"),
        (RetrievalDependencyError("DENSE_SEARCH", "PostgreSQL is unavailable"), 503, "DENSE_SEARCH"),
        (RetrievalError("FUSION", "Unexpected internal retrieval error"), 500, "FUSION"),
    ]
    for error, status, stage in cases:
        override(CapturingService(error=error))
        response = client.post("/retrieve", json={"query_text": "legal query"})
        assert response.status_code == status
        assert response.json()["detail"]["stage"] == stage


def _canonical_document_id(db):
    return db.execute(
        text(
            """
            SELECT d.id
            FROM documents d
            WHERE d.filename = 'sample_legal.pdf'
              AND EXISTS (
                  SELECT 1 FROM chunk_indexes ci
                  WHERE ci.document_id = d.id
                    AND ci.index_version = 'block3-v1'
              )
            ORDER BY d.created_at
            LIMIT 1
            """
        )
    ).scalar_one()


def test_live_dense_lexical_filtering_and_hybrid_e2e():
    db = SessionLocal()
    try:
        document_id = _canonical_document_id(db)
        other_document_id = db.execute(
            text(
                """
                SELECT document_id FROM chunk_indexes
                WHERE document_id <> :document_id
                  AND index_version = 'block3-v1'
                LIMIT 1
                """
            ),
            {"document_id": document_id},
        ).scalar_one()
        assert other_document_id != document_id
        repository = RetrievalRepository(db)
        vector = QueryEmbedder.get_instance().encode("doanh nghiệp điện được hưởng ưu đãi gì")
        dense = repository.dense_search(vector, 10, [document_id])
        lexical = repository.lexical_search("cơ chế chính sách ưu đãi", 10, [document_id])
        fused = reciprocal_rank_fusion(dense, lexical, 60, 5)
        hydrated = repository.hydrate([item.chunk_id for item in fused])

        assert dense
        assert lexical
        assert fused
        assert all(item.document_id == document_id for item in dense)
        assert all(item.document_id == document_id for item in lexical)
        assert all(item.document_id == document_id for item in fused)
        assert [item.dense_rank for item in dense] == list(range(1, len(dense) + 1))
        assert [item.lexical_rank for item in lexical] == list(range(1, len(lexical) + 1))
        assert set(hydrated) == {item.chunk_id for item in fused}
        assert repository.lexical_search(
            "xyzzynonexistenttoken", 10, [document_id]
        ) == []
    finally:
        db.close()


def test_live_wrong_document_is_never_returned_and_zero_results():
    db = SessionLocal()
    try:
        missing_document_id = uuid4()
        repository = RetrievalRepository(db)
        vector = np.eye(1, 768, dtype=np.float32)[0]
        assert repository.dense_search(vector, 5, [missing_document_id]) == []
        assert repository.lexical_search("ưu đãi", 5, [missing_document_id]) == []

        params = validate_request(
            RetrievalRequest(
                query_text="valid nonsense xyzzyplugh",
                document_ids=[str(missing_document_id)],
            )
        )
        assert RetrievalService(db).retrieve(params) == []
    finally:
        db.close()


def test_live_safe_lexical_fallback_handles_natural_vietnamese_and_hostile_syntax():
    db = SessionLocal()
    try:
        repository = RetrievalRepository(db)
        document_id = _canonical_document_id(db)
        natural = repository.lexical_search(
            "Đơn vị vận hành có được ưu tiên tham gia dự án đầu tư sử dụng vốn ODA không?",
            50,
            [document_id],
        )
        assert natural
        assert str(natural[0].chunk_id) == "b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4"
        assert [item.lexical_rank for item in natural] == list(range(1, len(natural) + 1))
        assert len(natural) <= 50

        filtered = repository.lexical_search(
            "Trụ sở của đơn vị vận hành bao gồm những trung tâm điều khiển nào?",
            50,
            [document_id],
        )
        assert filtered and all(item.document_id == document_id for item in filtered)

        assert repository.lexical_search("... !!! ???", 50, []) == []
        for query in ('" OR !:* & <->', "' ; DROP TABLE chunks; --", "ODA ODA ODA vốn"):
            result = repository.lexical_search(query, 50, [])
            assert isinstance(result, list)
    finally:
        db.close()
