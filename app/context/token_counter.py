from typing import Protocol, runtime_checkable


@runtime_checkable
class TokenCounter(Protocol):
    """Exact tokenizer contract supplied by a future Generation Profile."""

    provider: str | None
    tokenizer_id: str | None

    def count(self, text: str) -> int:
        """Return the exact token count for text."""
        ...
