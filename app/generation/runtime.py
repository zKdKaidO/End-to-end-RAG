from app.core.config import settings
from app.generation.ollama import OllamaAdapter


_client: OllamaAdapter | None = None


def get_llm_client() -> OllamaAdapter:
    global _client
    if _client is None:
        _client = OllamaAdapter(settings.OLLAMA_BASE_URL, settings.GENERATION_REQUEST_TIMEOUT_SECONDS)
    return _client


async def close_llm_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
