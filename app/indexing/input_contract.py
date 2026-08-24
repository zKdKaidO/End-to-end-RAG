"""Canonical multilingual-E5 input rules shared by Blocks 2 and 3."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from transformers import AutoTokenizer


EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-base"
PASSAGE_PREFIX = "passage: "
MODEL_MAX_SEQUENCE_LENGTH = 512

# Packing heuristics only. Exact final-input tokenization remains authoritative.
TOKEN_SAFETY_HEADROOM = 4
MIN_CONTENT_TOKENS = 16
HARD_SPLIT_OVERLAP_TOKENS = 30
MIN_FORWARD_PROGRESS_TOKENS = 8


class EmbeddingHeaderTooLongError(ValueError):
    def __init__(
        self,
        fixed_token_count: int,
        available_content_tokens: int,
        minimum_content_tokens: int = MIN_CONTENT_TOKENS,
    ):
        self.fixed_token_count = fixed_token_count
        self.available_content_tokens = available_content_tokens
        self.minimum_content_tokens = minimum_content_tokens
        super().__init__(
            "Embedding header leaves insufficient content capacity: "
            f"fixed_tokens={fixed_token_count}, "
            f"available_content_tokens={available_content_tokens}, "
            f"minimum={minimum_content_tokens}"
        )


class EmbeddingInputContractViolation(ValueError):
    def __init__(self, chunk_ref: str, token_count: int, max_tokens: int):
        self.chunk_ref = chunk_ref
        self.token_count = token_count
        self.max_tokens = max_tokens
        super().__init__(
            f"Chunk {chunk_ref} exact final E5 token count {token_count} "
            f"exceeds limit {max_tokens}"
        )


class E5InputContract:
    def __init__(self, tokenizer: Any, max_tokens: int = MODEL_MAX_SEQUENCE_LENGTH):
        if not getattr(tokenizer, "is_fast", False):
            raise ValueError("Token-safe source slicing requires a Hugging Face fast tokenizer")
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        self.tokenizer = tokenizer
        self.max_tokens = max_tokens

    @staticmethod
    def build_final_input(embedding_text: str) -> str:
        return f"{PASSAGE_PREFIX}{embedding_text}"

    def count_final_tokens(self, embedding_text: str) -> int:
        return len(
            self.tokenizer.encode(
                self.build_final_input(embedding_text),
                add_special_tokens=True,
                truncation=False,
            )
        )

    def count_tokens(self, final_input: str) -> int:
        return len(
            self.tokenizer.encode(
                final_input,
                add_special_tokens=True,
                truncation=False,
            )
        )

    def fits(self, embedding_text: str) -> bool:
        return self.count_final_tokens(embedding_text) <= self.max_tokens

    def validate(self, chunk_ref: str, embedding_text: str) -> int:
        token_count = self.count_final_tokens(embedding_text)
        if token_count > self.max_tokens:
            raise EmbeddingInputContractViolation(chunk_ref, token_count, self.max_tokens)
        return token_count

    def content_offsets(self, source_text: str) -> list[tuple[int, int]]:
        encoded = self.tokenizer(
            source_text,
            add_special_tokens=False,
            return_offsets_mapping=True,
            truncation=False,
        )
        return [
            (int(start), int(end))
            for start, end in encoded["offset_mapping"]
            if int(end) > int(start)
        ]


@lru_cache(maxsize=1)
def get_e5_input_contract() -> E5InputContract:
    """Load only the cached tokenizer; no SentenceTransformer weights."""
    tokenizer = AutoTokenizer.from_pretrained(
        EMBEDDING_MODEL_NAME,
        local_files_only=True,
        use_fast=True,
    )
    if tokenizer.model_max_length != MODEL_MAX_SEQUENCE_LENGTH:
        raise ValueError(
            "Unexpected multilingual-E5 tokenizer limit: "
            f"{tokenizer.model_max_length} != {MODEL_MAX_SEQUENCE_LENGTH}"
        )
    return E5InputContract(tokenizer, MODEL_MAX_SEQUENCE_LENGTH)
