from concurrent.futures import ThreadPoolExecutor
import threading
import time

import numpy as np
import pytest

from app.retrieval.exceptions import QueryInputTooLongError, RetrievalDependencyError
from app.retrieval.query_embedder import QueryEmbedder


class FakeTokenizer:
    def __init__(self, token_count=3):
        self.token_count = token_count

    def encode(self, text):
        return list(range(self.token_count))


class FakeModel:
    def __init__(self, vector=None, token_count=3):
        self.tokenizer = FakeTokenizer(token_count)
        self.vector = vector if vector is not None else np.eye(1, 768, dtype=np.float32)[0]
        self.calls = []

    def encode(self, texts, **kwargs):
        self.calls.append((texts, kwargs))
        return np.asarray([self.vector])


class FakeBaseEmbedder:
    model_name = "intfloat/multilingual-e5-base"
    embedding_dimension = 768
    max_tokens = 512

    def __init__(self, model):
        self.model = model
        self.inference_lock = threading.RLock()


class RaceDetectingState:
    """Raises exactly like a borrowed FastTokenizer if calls overlap."""

    def __init__(self):
        self._lock = threading.Lock()
        self.active = 0
        self.max_active = 0

    def run(self, callback):
        with self._lock:
            if self.active:
                raise RuntimeError("Already borrowed")
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            time.sleep(0.001)
            return callback()
        finally:
            with self._lock:
                self.active -= 1


class RaceDetectingTokenizer:
    def __init__(self, state):
        self.state = state

    def encode(self, text):
        return self.state.run(lambda: [0, 1, 2])


class RaceDetectingModel:
    def __init__(self, state):
        self.tokenizer = RaceDetectingTokenizer(state)
        self.state = state

    def encode(self, texts, **_kwargs):
        def build_vectors():
            vectors = np.zeros((len(texts), 768), dtype=np.float32)
            for row, text in enumerate(texts):
                vectors[row, int(text.rsplit("-", maxsplit=1)[1])] = 1.0
            return vectors

        return self.state.run(build_vectors)


def test_query_prefix_and_normalized_dimension():
    model = FakeModel()
    embedder = QueryEmbedder(FakeBaseEmbedder(model))

    vector = embedder.encode("Doanh nghiệp được hưởng ưu đãi gì?")

    assert model.calls[0][0] == ["query: Doanh nghiệp được hưởng ưu đãi gì?"]
    assert model.calls[0][1]["normalize_embeddings"] is True
    assert vector.shape == (768,)
    assert np.isfinite(vector).all()
    assert np.isclose(np.linalg.norm(vector), 1.0, atol=1e-5)


def test_query_too_long_is_rejected_without_encoding():
    model = FakeModel(token_count=513)
    embedder = QueryEmbedder(FakeBaseEmbedder(model))

    with pytest.raises(QueryInputTooLongError) as exc_info:
        embedder.encode("long query")

    assert exc_info.value.token_count == 513
    assert exc_info.value.max_tokens == 512
    assert model.calls == []


def test_query_at_the_existing_token_limit_is_encoded():
    model = FakeModel(token_count=512)
    embedder = QueryEmbedder(FakeBaseEmbedder(model))

    vector = embedder.encode("boundary query")

    assert vector.shape == (768,)
    assert len(model.calls) == 1


@pytest.mark.parametrize(
    "vector,message",
    [
        (np.ones(767, dtype=np.float32), "dimension"),
        (np.full(768, np.nan, dtype=np.float32), "non-finite"),
        (np.ones(768, dtype=np.float32), "non-normalized"),
    ],
)
def test_invalid_model_output_is_rejected(vector, message):
    embedder = QueryEmbedder(FakeBaseEmbedder(FakeModel(vector=vector)))
    with pytest.raises(RetrievalDependencyError, match=message):
        embedder.encode("query")


def test_query_embedder_singleton_and_block3_model_are_reused():
    first = QueryEmbedder.get_instance()
    second = QueryEmbedder.get_instance()
    assert first is second
    assert first._base_embedder is second._base_embedder


@pytest.mark.parametrize("callers,iterations_per_caller", [(1, 20), (5, 20), (10, 20)])
def test_shared_query_embedder_serializes_fast_tokenizer_and_model_calls(
    callers, iterations_per_caller
):
    state = RaceDetectingState()
    embedder = QueryEmbedder(FakeBaseEmbedder(RaceDetectingModel(state)))

    def encode(index):
        vector = embedder.encode(f"concurrent-query-{index % 10}")
        return index % 10, vector

    with ThreadPoolExecutor(max_workers=callers) as executor:
        outputs = list(executor.map(encode, range(callers * iterations_per_caller)))

    assert len(outputs) == callers * iterations_per_caller
    assert state.max_active == 1
    for expected_index, vector in outputs:
        assert vector.shape == (768,)
        assert np.isfinite(vector).all()
        assert np.isclose(np.linalg.norm(vector), 1.0, atol=1e-5)
        assert vector[expected_index] == 1.0


def test_real_query_embedding_smoke():
    embedder = QueryEmbedder.get_instance()
    vector = embedder.encode("cơ chế chính sách ưu đãi hệ thống điện")
    assert embedder.model_name == "intfloat/multilingual-e5-base"
    assert vector.shape == (768,)
    assert np.isfinite(vector).all()
    assert np.isclose(np.linalg.norm(vector), 1.0, atol=1e-5)
