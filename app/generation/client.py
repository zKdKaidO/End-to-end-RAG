from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol

from app.generation.profile import GenerationProfile
from app.generation.schemas import Usage


@dataclass(frozen=True)
class LLMResult:
    text: str
    finish_reason: str | None
    usage: Usage | None


@dataclass(frozen=True)
class LLMStreamChunk:
    text: str = ""
    done: bool = False
    finish_reason: str | None = None
    usage: Usage | None = None


class LLMClient(Protocol):
    async def health(self, profile: GenerationProfile) -> None: ...

    async def generate(
        self, messages: list[dict[str, Any]], profile: GenerationProfile
    ) -> LLMResult: ...

    def stream(
        self, messages: list[dict[str, Any]], profile: GenerationProfile
    ) -> AsyncIterator[LLMStreamChunk]: ...

    async def close(self) -> None: ...
