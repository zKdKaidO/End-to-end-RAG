import os
import torch
import numpy as np
from sentence_transformers import SentenceTransformer

class EmbeddingInputTooLongError(Exception):
    def __init__(self, chunk_id: str, token_count: int, max_tokens: int):
        self.chunk_id = chunk_id
        self.token_count = token_count
        self.max_tokens = max_tokens
        super().__init__(f"Chunk {chunk_id} token count {token_count} exceeds limit {max_tokens}")

class E5Embedder:
    _instance = None
    _model_name = "intfloat/multilingual-e5-base"

    def __init__(self):
        # Determine device
        device = os.environ.get("EMBEDDING_DEVICE", "cpu")
        self.model = SentenceTransformer(self._model_name, device=device)
        self.max_tokens = self.model.max_seq_length

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def validate_token_length(self, chunk_id: str, passage: str):
        # We can use the tokenizer directly
        tokens = self.model.tokenizer.encode(passage)
        # SentenceTransformer max_seq_length
        if len(tokens) > self.max_tokens:
            raise EmbeddingInputTooLongError(chunk_id, len(tokens), self.max_tokens)

    def encode_batch(self, chunks_with_ids: list[tuple[str, str]]) -> list[np.ndarray]:
        if not chunks_with_ids:
            return []

        passages = []
        for chunk_id, text in chunks_with_ids:
            # Prefix for E5 models
            passage = f"passage: {text}"
            self.validate_token_length(chunk_id, passage)
            passages.append(passage)

        # encode with normalize_embeddings=True to get L2 normalized float32 vectors
        embeddings = self.model.encode(
            passages,
            batch_size=len(passages),
            normalize_embeddings=True,
            convert_to_numpy=True
        )

        return embeddings

    @property
    def embedding_dimension(self) -> int:
        return 768

    @property
    def model_name(self) -> str:
        return self._model_name
