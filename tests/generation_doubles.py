from dataclasses import dataclass, field

from app.generation.client import LLMResult, LLMStreamChunk
from app.generation.schemas import Usage


@dataclass
class FixedPromptCounter:
    value: int = 100
    calls: list = field(default_factory=list)

    def count_messages(self, messages):
        self.calls.append(messages)
        return self.value


@dataclass
class FakeLLMClient:
    text: str = "[STATUS: ANSWERABLE]\nNội dung trả lời [S1]"
    chunks: tuple[str, ...] = ("[STATUS: ANSWERABLE]\nNội dung ", "trả lời [S1]")
    generate_calls: int = 0
    stream_calls: int = 0
    closed: bool = False

    async def health(self, profile):
        return None

    async def generate(self, messages, profile):
        self.generate_calls += 1
        return LLMResult(self.text, "stop", Usage(input_tokens=100, output_tokens=8, total_tokens=108))

    async def stream(self, messages, profile):
        self.stream_calls += 1
        for text in self.chunks:
            yield LLMStreamChunk(text=text)
        yield LLMStreamChunk(done=True, finish_reason="stop", usage=Usage(input_tokens=100, output_tokens=8, total_tokens=108))

    async def close(self):
        self.closed = True


class FakeRetrievalService:
    def __init__(self, results):
        self.results = results
        self.calls = 0

    def retrieve(self, params):
        self.calls += 1
        return self.results
