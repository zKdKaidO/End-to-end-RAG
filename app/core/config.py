from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "End-to-End RAG (Block 1)"
    LOG_LEVEL: str = "INFO"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    APP_ENV: str = "development"
    DEBUG_UI_ENABLED: bool = False
    DEBUG_UI_ORIGINS: str = "http://localhost:5173"

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # MinIO
    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str = "documents"
    MINIO_SECURE: bool = False

    # Block 4 frozen defaults and safety bounds. Limits reject excessive work
    # and never clamp caller values.
    RETRIEVAL_TOP_K_DENSE_DEFAULT: int = 50
    RETRIEVAL_TOP_K_LEXICAL_DEFAULT: int = 50
    RETRIEVAL_TOP_K_FINAL_DEFAULT: int = 10
    RETRIEVAL_RRF_K_DEFAULT: int = 60
    RETRIEVAL_MAX_TOP_K_DENSE: int = 200
    RETRIEVAL_MAX_TOP_K_LEXICAL: int = 200
    RETRIEVAL_MAX_TOP_K_FINAL: int = 100
    RETRIEVAL_MAX_RRF_K: int = 10_000
    RETRIEVAL_MAX_DOCUMENT_IDS: int = 100

    # Legal Hierarchy Retrieval V2. These controls are server-owned and are
    # intentionally absent from public retrieval/answer request schemas.
    RETRIEVAL_HIERARCHY_ENABLED: bool = True
    RETRIEVAL_HIERARCHY_MAX_ANCHORS: int = 10
    RETRIEVAL_HIERARCHY_MAX_CHILDREN_PER_ANCHOR: int = 4
    RETRIEVAL_HIERARCHY_MAX_CANDIDATES_ADDED: int = 20
    RETRIEVAL_HIERARCHY_DEPTH: int = 1

    # Block 6 server-owned generation profile.
    GENERATION_PROVIDER: str = "ollama"
    GENERATION_MODEL_ID: str = "qwen3.5:9b"
    GENERATION_TOKENIZER_PROVIDER: str = "huggingface"
    GENERATION_TOKENIZER_ID: str = "Qwen/Qwen3.5-9B"
    GENERATION_MODEL_CONTEXT_LIMIT: int = 32_768
    GENERATION_CONTEXT_BUDGET_TOKENS: int = 4_096
    GENERATION_MAX_OUTPUT_TOKENS: int = 512
    GENERATION_PROMPT_TOKEN_SAFETY_MARGIN: int = 32
    GENERATION_THINKING: bool = False
    GENERATION_TEMPERATURE: float = 0.0
    GENERATION_TOP_P: float = 0.9
    GENERATION_TOP_K: int = 20
    GENERATION_PROMPT_VERSION: str = "legal-rag-v2"
    GENERATION_REQUEST_TIMEOUT_SECONDS: float = 180.0
    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
