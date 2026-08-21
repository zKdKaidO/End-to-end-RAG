import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.generation.client import LLMResult, LLMStreamChunk
from app.generation.exceptions import (
    GenerationDependencyError,
    GenerationTimeoutError,
)
from app.generation.profile import GenerationProfile
from app.generation.schemas import Usage


class OllamaAdapter:
    """One pooled async client for the isolated local Ollama runtime."""

    def __init__(self, base_url: str, timeout_seconds: float):
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds),
        )

    @staticmethod
    def _payload(messages: list[dict[str, Any]], profile: GenerationProfile, stream: bool) -> dict[str, Any]:
        return {
            "model": profile.model_id,
            "messages": messages,
            "stream": stream,
            "think": profile.thinking,
            "keep_alive": "10m",
            "options": {
                "temperature": profile.temperature,
                "top_p": profile.top_p,
                "top_k": profile.top_k,
                "num_predict": profile.max_output_tokens,
                "num_ctx": profile.model_context_limit,
            },
        }

    @staticmethod
    def _usage(data: dict[str, Any]) -> Usage | None:
        input_tokens = data.get("prompt_eval_count")
        output_tokens = data.get("eval_count")
        if input_tokens is None and output_tokens is None:
            return None
        total = input_tokens + output_tokens if isinstance(input_tokens, int) and isinstance(output_tokens, int) else None
        return Usage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total)

    async def health(self, profile: GenerationProfile) -> None:
        try:
            response = await self._client.get("/api/tags")
            response.raise_for_status()
            models = {item.get("name") for item in response.json().get("models", [])}
            if profile.model_id not in models:
                raise GenerationDependencyError(
                    "LLM_REQUEST", "MODEL_UNAVAILABLE", f"Configured model {profile.model_id} is not installed"
                )
        except GenerationDependencyError:
            raise
        except httpx.TimeoutException as exc:
            raise GenerationTimeoutError("LLM_REQUEST", "PROVIDER_TIMEOUT", "Generation provider timed out") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise GenerationDependencyError("LLM_REQUEST", "PROVIDER_UNAVAILABLE", "Generation provider is unavailable") from exc

    async def generate(self, messages: list[dict[str, Any]], profile: GenerationProfile) -> LLMResult:
        try:
            response = await self._client.post("/api/chat", json=self._payload(messages, profile, False))
            response.raise_for_status()
            data = response.json()
            return LLMResult(
                text=data.get("message", {}).get("content", ""),
                finish_reason=data.get("done_reason"),
                usage=self._usage(data),
            )
        except httpx.TimeoutException as exc:
            raise GenerationTimeoutError("LLM_REQUEST", "PROVIDER_TIMEOUT", "Generation provider timed out") from exc
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise GenerationDependencyError("LLM_REQUEST", "PROVIDER_UNAVAILABLE", "Generation provider is unavailable") from exc

    async def stream(self, messages: list[dict[str, Any]], profile: GenerationProfile) -> AsyncIterator[LLMStreamChunk]:
        try:
            async with self._client.stream("POST", "/api/chat", json=self._payload(messages, profile, True)) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("error"):
                        raise GenerationDependencyError("STREAMING", "PROVIDER_STREAM_ERROR", "Generation stream failed")
                    text = data.get("message", {}).get("content", "")
                    if text:
                        yield LLMStreamChunk(text=text)
                    if data.get("done"):
                        yield LLMStreamChunk(
                            done=True,
                            finish_reason=data.get("done_reason"),
                            usage=self._usage(data),
                        )
        except GenerationDependencyError:
            raise
        except httpx.TimeoutException as exc:
            raise GenerationTimeoutError("STREAMING", "PROVIDER_TIMEOUT", "Generation provider timed out") from exc
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise GenerationDependencyError("STREAMING", "PROVIDER_STREAM_ERROR", "Generation stream failed") from exc

    async def close(self) -> None:
        await self._client.aclose()
