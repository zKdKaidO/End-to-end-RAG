from uuid import UUID

import numpy as np

from app.retrieval.schemas import RetrievalRequest
from app.retrieval.service import RetrievalService, validate_request
from app.retrieval.types import DenseCandidate, HydratedChunk, LexicalCandidate


DOC = UUID("00000000-0000-0000-0000-000000000010")
CHUNK_A = UUID("00000000-0000-0000-0000-000000000001")
CHUNK_B = UUID("00000000-0000-0000-0000-000000000002")


class FakeEmbedder:
    def encode(self, query_text):
        return np.eye(1, 768, dtype=np.float32)[0]


class FakeRepository:
    def __init__(self, dense=None, lexical=None):
        self.dense = dense or []
        self.lexical = lexical or []
        self.hydrate_calls = []

    def dense_search(self, *args):
        return self.dense

    def lexical_search(self, *args):
        return self.lexical

    def hydrate(self, chunk_ids):
        self.hydrate_calls.append(chunk_ids)
        # Deliberately construct reverse insertion order; service must restore RRF order.
        return {
            chunk_id: HydratedChunk(
                chunk_id, DOC, f"content {chunk_id.int}", {"id": chunk_id.int}, {"page": 1}
            )
            for chunk_id in reversed(chunk_ids)
        }


def test_defaults_deduplication_and_minimal_normalization():
    params = validate_request(
        RetrievalRequest(
            query_text="  legal query  ", document_ids=[str(DOC), str(DOC)]
        )
    )
    assert params.query_text == "legal query"
    assert params.top_k_dense == 50
    assert params.top_k_lexical == 50
    assert params.top_k_final == 10
    assert params.rrf_k == 60
    assert params.document_ids == (DOC,)


def test_service_restores_final_order_and_hydrates_once():
    repo = FakeRepository(
        dense=[
            DenseCandidate(CHUNK_A, DOC, 0.9, 1),
            DenseCandidate(CHUNK_B, DOC, 0.8, 2),
        ],
        lexical=[LexicalCandidate(CHUNK_B, DOC, 0.5, 1)],
    )
    params = validate_request(RetrievalRequest(query_text="legal query"))
    results = RetrievalService(None, FakeEmbedder(), repo).retrieve(params)

    assert len(repo.hydrate_calls) == 1
    assert [item["chunk_id"] for item in results] == [str(CHUNK_B), str(CHUNK_A)]
    assert [item["final_rank"] for item in results] == [1, 2]
    assert results[0]["metadata_json"] == {"id": 2}
    assert results[0]["provenance_json"] == {"page": 1}


def test_both_empty_returns_empty_and_skips_hydration_sql():
    repo = FakeRepository()
    params = validate_request(RetrievalRequest(query_text="valid nonsense"))
    results = RetrievalService(None, FakeEmbedder(), repo).retrieve(params)
    assert results == []
    assert repo.hydrate_calls == [[]]
