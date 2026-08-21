from dataclasses import dataclass, field


@dataclass
class CharacterTokenCounter:
    """Deterministic additive test double; one Unicode code point is one token."""

    provider: str | None = "test"
    tokenizer_id: str | None = "unicode-codepoint-v1"
    calls: list[str] = field(default_factory=list)

    def count(self, text: str) -> int:
        self.calls.append(text)
        return len(text)


@dataclass
class FailingTokenCounter:
    provider: str | None = "test"
    tokenizer_id: str | None = "failing-v1"

    def count(self, text: str) -> int:
        raise RuntimeError("tokenizer unavailable")
