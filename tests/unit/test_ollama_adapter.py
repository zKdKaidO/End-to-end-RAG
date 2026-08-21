import json

import httpx
import pytest

from app.generation.ollama import OllamaAdapter
from app.generation.profile import get_generation_profile


@pytest.mark.asyncio
async def test_ollama_nonstream_payload_usage_and_thinking_disabled():
    captured = {}

    async def handler(request):
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "Trả lời [S1]", "thinking": "private"},
                "done_reason": "stop",
                "prompt_eval_count": 20,
                "eval_count": 5,
            },
        )

    adapter = OllamaAdapter("http://ollama.test", 10)
    await adapter._client.aclose()
    adapter._client = httpx.AsyncClient(base_url="http://ollama.test", transport=httpx.MockTransport(handler))
    try:
        result = await adapter.generate([{"role": "user", "content": "q"}], get_generation_profile())
    finally:
        await adapter.close()
    assert result.text == "Trả lời [S1]"
    assert "private" not in result.text
    assert result.usage.total_tokens == 25
    assert captured["stream"] is False and captured["think"] is False
    assert captured["model"] == "qwen3.5:9b"


@pytest.mark.asyncio
async def test_ollama_health_verifies_configured_model():
    async def handler(request):
        return httpx.Response(200, json={"models": [{"name": "qwen3.5:9b"}]})

    adapter = OllamaAdapter("http://ollama.test", 10)
    await adapter._client.aclose()
    adapter._client = httpx.AsyncClient(base_url="http://ollama.test", transport=httpx.MockTransport(handler))
    try:
        await adapter.health(get_generation_profile())
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_ollama_stream_maps_deltas_and_terminal_usage():
    lines = [
        {"message": {"content": "A"}, "done": False},
        {"message": {"content": " [S1]"}, "done": False},
        {"message": {"content": ""}, "done": True, "done_reason": "stop", "prompt_eval_count": 10, "eval_count": 3},
    ]

    async def handler(request):
        return httpx.Response(200, content="".join(json.dumps(line) + "\n" for line in lines))

    adapter = OllamaAdapter("http://ollama.test", 10)
    await adapter._client.aclose()
    adapter._client = httpx.AsyncClient(base_url="http://ollama.test", transport=httpx.MockTransport(handler))
    try:
        chunks = [chunk async for chunk in adapter.stream([{"role": "user", "content": "q"}], get_generation_profile())]
    finally:
        await adapter.close()
    assert [chunk.text for chunk in chunks if chunk.text] == ["A", " [S1]"]
    assert chunks[-1].done is True
    assert chunks[-1].usage.total_tokens == 13
