import torch
import numpy as np
from sentence_transformers import SentenceTransformer
from app.core.config import settings
from app.indexing.input_contract import E5InputContract, EMBEDDING_MODEL_NAME

class EmbeddingInputTooLongError(Exception):
    def __init__(self, chunk_id: str, token_count: int, max_tokens: int):
        self.chunk_id = chunk_id
        self.token_count = token_count
        self.max_tokens = max_tokens
        super().__init__(f"Chunk {chunk_id} token count {token_count} exceeds limit {max_tokens}")

class E5Embedder:
    _instance = None
    _model_name = EMBEDDING_MODEL_NAME

    def __init__(self):
        # Determine device
        device = settings.EMBEDDING_DEVICE
        self.model = SentenceTransformer(
            self._model_name,
            device=device,
            cache_folder=settings.EMBEDDING_MODEL_CACHE_DIR,
        )
        self.max_tokens = self.model.max_seq_length
        self.input_contract = E5InputContract(self.model.tokenizer, self.max_tokens)

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def validate_token_length(self, chunk_id: str, passage: str):
        # Validate the exact final prefixed input. Block 3 remains defensive.
        token_count = self.input_contract.count_tokens(passage)
        # SentenceTransformer max_seq_length
        if token_count > self.max_tokens:
            raise EmbeddingInputTooLongError(chunk_id, token_count, self.max_tokens)

    def encode_batch(self, chunks_with_ids: list[tuple[str, str]]) -> list[np.ndarray]:
        if not chunks_with_ids:
            return []

        passages = []
        for chunk_id, text in chunks_with_ids:
            # Prefix for E5 models
            passage = self.input_contract.build_final_input(text)
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
