from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationProfile:
    provider: str
    model_id: str
    tokenizer_provider: str
    tokenizer_id: str
    model_context_limit: int
    context_budget_tokens: int
    max_output_tokens: int
    prompt_token_safety_margin: int
    thinking: bool
    temperature: float
    top_p: float
    top_k: int
    prompt_version: str
    request_timeout_seconds: float

    def validate(self) -> None:
        if self.provider != "ollama":
            raise ValueError("unsupported generation provider")
        if not self.model_id.strip() or not self.tokenizer_id.strip():
            raise ValueError("model and tokenizer identifiers are required")
        if self.model_context_limit <= 0 or self.context_budget_tokens <= 0:
            raise ValueError("token limits must be positive")
        if self.max_output_tokens <= 0 or self.max_output_tokens >= self.model_context_limit:
            raise ValueError("max_output_tokens must be below model_context_limit")
        if self.prompt_token_safety_margin < 0:
            raise ValueError("prompt token safety margin cannot be negative")
        if self.context_budget_tokens + self.max_output_tokens + self.prompt_token_safety_margin >= self.model_context_limit:
            raise ValueError("generation token budgets are internally inconsistent")
        if not 0 <= self.temperature <= 2 or not 0 < self.top_p <= 1 or self.top_k <= 0:
            raise ValueError("sampling configuration is invalid")
        if self.request_timeout_seconds <= 0:
            raise ValueError("request timeout must be positive")
        if self.prompt_version not in {"legal-rag-v1", "legal-rag-v2", "legal-rag-v3"}:
            raise ValueError("unknown prompt version")


def get_generation_profile() -> GenerationProfile:
    # Resolve server configuration at the point the production profile is
    # requested, not while importing the shared profile value object.  The
    # desktop runtime supplies an explicit local profile instead.
    from app.core.config import settings

    profile = GenerationProfile(
        provider=settings.GENERATION_PROVIDER,
        model_id=settings.GENERATION_MODEL_ID,
        tokenizer_provider=settings.GENERATION_TOKENIZER_PROVIDER,
        tokenizer_id=settings.GENERATION_TOKENIZER_ID,
        model_context_limit=settings.GENERATION_MODEL_CONTEXT_LIMIT,
        context_budget_tokens=settings.GENERATION_CONTEXT_BUDGET_TOKENS,
        max_output_tokens=settings.GENERATION_MAX_OUTPUT_TOKENS,
        prompt_token_safety_margin=settings.GENERATION_PROMPT_TOKEN_SAFETY_MARGIN,
        thinking=settings.GENERATION_THINKING,
        temperature=settings.GENERATION_TEMPERATURE,
        top_p=settings.GENERATION_TOP_P,
        top_k=settings.GENERATION_TOP_K,
        prompt_version=settings.GENERATION_PROMPT_VERSION,
        request_timeout_seconds=settings.GENERATION_REQUEST_TIMEOUT_SECONDS,
    )
    profile.validate()
    return profile
