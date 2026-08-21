from functools import lru_cache
from typing import Any

from transformers import AutoTokenizer


@lru_cache(maxsize=4)
def _load_tokenizer(tokenizer_id: str):
    return AutoTokenizer.from_pretrained(tokenizer_id)


class ContextTokenCounter:
    def __init__(self, provider: str, tokenizer_id: str):
        self.provider = provider
        self.tokenizer_id = tokenizer_id
        self._tokenizer = _load_tokenizer(tokenizer_id)

    def count(self, text: str) -> int:
        return len(self._tokenizer.encode(text, add_special_tokens=False))


class PromptTokenCounter:
    def __init__(self, provider: str, tokenizer_id: str, *, thinking: bool = False):
        self.provider = provider
        self.tokenizer_id = tokenizer_id
        self.thinking = thinking
        self._tokenizer = _load_tokenizer(tokenizer_id)

    def count_messages(self, messages: list[dict[str, Any]]) -> int:
        encoded = self._tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            enable_thinking=self.thinking,
        )
        return len(encoded["input_ids"])
