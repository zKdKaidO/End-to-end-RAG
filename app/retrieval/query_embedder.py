import math
import threading

import numpy as np

from app.indexing.embedder import E5Embedder
from app.retrieval.exceptions import QueryInputTooLongError, RetrievalDependencyError


class QueryEmbedder:
    """Reusable E5 query encoder backed by the frozen Block 3 model singleton."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self, base_embedder: E5Embedder | None = None):
        self._base_embedder = base_embedder or E5Embedder.get_instance()

    @classmethod
    def get_instance(cls) -> "QueryEmbedder":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def model_name(self) -> str:
        return self._base_embedder.model_name

    @property
    def embedding_dimension(self) -> int:
        return self._base_embedder.embedding_dimension

    @property
    def max_tokens(self) -> int:
        return self._base_embedder.max_tokens

    def encode(self, query_text: str) -> np.ndarray:
        prefixed_query = f"query: {query_text}"
        token_count = len(self._base_embedder.model.tokenizer.encode(prefixed_query))
        if token_count > self.max_tokens:
            raise QueryInputTooLongError(token_count, self.max_tokens)

        try:
            encoded = self._base_embedder.model.encode(
                [prefixed_query],
                batch_size=1,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
        except QueryInputTooLongError:
            raise
        except Exception as exc:
            raise RetrievalDependencyError(
                "QUERY_EMBEDDING", "Embedding model is unavailable"
            ) from exc

        vector = np.asarray(encoded[0], dtype=np.float32)
        if vector.shape != (768,):
            raise RetrievalDependencyError(
                "QUERY_EMBEDDING",
                f"Embedding model returned dimension {vector.size}; expected 768",
            )
        if not np.isfinite(vector).all():
            raise RetrievalDependencyError(
                "QUERY_EMBEDDING", "Embedding model returned non-finite values"
            )

        norm = float(np.linalg.norm(vector))
        if not math.isclose(norm, 1.0, rel_tol=0.0, abs_tol=1e-4):
            raise RetrievalDependencyError(
                "QUERY_EMBEDDING",
                f"Embedding model returned a non-normalized vector (norm={norm:.6f})",
            )
        return vector
