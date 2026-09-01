from enum import Enum

from pydantic_settings import BaseSettings, SettingsConfigDict


class DeploymentProfile(str, Enum):
    """Deployment topology only; RAG behavior is intentionally profile-neutral."""

    LOCAL_DEV = "local_dev"
    PC_TUNNEL = "pc_tunnel"
    SELF_HOSTED = "self_hosted"
    CLOUD_CONTROL_PLANE = "cloud_control_plane"
    BENCHMARK = "benchmark"


_DEPLOYMENT_PROFILE_ALIASES = {
    "development": DeploymentProfile.LOCAL_DEV,
    "production": DeploymentProfile.SELF_HOSTED,
}


def resolve_deployment_profile(value: str) -> DeploymentProfile:
    normalized = str(value or "").strip().casefold()
    if normalized in _DEPLOYMENT_PROFILE_ALIASES:
        return _DEPLOYMENT_PROFILE_ALIASES[normalized]
    try:
        return DeploymentProfile(normalized)
    except ValueError as exc:
        raise ValueError(f"UNKNOWN_DEPLOYMENT_PROFILE:{value}") from exc

class Settings(BaseSettings):
    PROJECT_NAME: str = "End-to-End RAG (Block 1)"
    LOG_LEVEL: str = "INFO"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    APP_ENV: str = "development"
    DEBUG_UI_ENABLED: bool = False
    EVALUATION_UI_ENABLED: bool = True
    DEBUG_UI_ORIGINS: str = "http://localhost:5173"

    # Product Auth + Authorization V1. Browser sessions are opaque and fixed
    # lifetime; production deployments must set AUTH_COOKIE_SECURE=true.
    AUTH_COOKIE_NAME: str = "legal_rag_session"
    AUTH_SESSION_TTL_SECONDS: int = 24 * 60 * 60
    AUTH_COOKIE_SECURE: bool = True
    AUTH_TRUSTED_ORIGINS: str = "http://localhost:5173"
    AUTH_PASSWORD_MIN_LENGTH: int = 12
    AUTH_PASSWORD_MAX_LENGTH: int = 1024
    AUTH_MAX_EXPLICIT_DOCUMENT_SCOPE: int = 100
    AUTH_LOGIN_RATE_PER_MINUTE: int = 10
    AUTH_LOGIN_BURST: int = 5
    AUTH_LOGIN_NETWORK_RATE_PER_MINUTE: int = 30
    AUTH_LOGIN_NETWORK_BURST: int = 10

    # P2C.5A platform control-plane metadata/signing only. An empty key is
    # fail-closed for grants outside development/test injection.
    COMPUTE_GRANT_SIGNING_KEY: str = ""
    COMPUTE_PAIRING_TTL_SECONDS: int = 300
    COMPUTE_LOCAL_SESSION_GRANT_TTL_SECONDS: int = 300
    COMPUTE_DEVICE_AUTH_WINDOW_SECONDS: int = 300
    COMPUTE_PRESENCE_FRESHNESS_SECONDS: int = 90

    # Security Hardening V1 boundary controls. Redis is authoritative so the
    # limits remain effective across API processes.
    CHAT_GENERATION_RATE_PER_MINUTE: int = 5
    CHAT_GENERATION_BURST: int = 2
    CHAT_MAX_ACTIVE_GENERATIONS_PER_USER: int = 1
    CHAT_MAX_GLOBAL_GENERATIONS: int = 1
    CHAT_GENERATION_LEASE_TTL_SECONDS: int = 240
    REQUEST_MAX_JSON_BYTES: int = 1024 * 1024
    REQUEST_MAX_QUERY_CHARS: int = 10_000
    REQUEST_ID_MAX_LENGTH: int = 128
    SECURITY_HSTS_ENABLED: bool = False

    # Deployment topology only. Legacy development/production values remain
    # accepted as aliases for local_dev/self_hosted during the transition.
    DEPLOYMENT_PROFILE: str = DeploymentProfile.LOCAL_DEV.value
    # Reserved for the physically isolated capacity benchmark environment.
    # It is never a user-selectable product runtime profile.
    BENCHMARK_RUNTIME_MARKER: str = ""
    RELEASE_ID: str = "development"
    EXPECTED_MODEL_DIGEST: str = ""
    TRUSTED_PROXY_CIDRS: str = ""
    RECOVERY_CONTROL_DIR: str = "tmp/recovery-control"
    BACKUP_DESTINATION: str = "tmp/backups"
    BACKUP_DESTINATION_ENCRYPTED: bool = False
    BACKUP_DESTINATION_SEPARATE_FAILURE_DOMAIN: bool = False
    BACKUP_RETENTION_DAYS: int = 30
    BACKUP_KEEP_LAST: int = 7
    BACKUP_SCHEDULE: str = "manual"
    RECOVERY_JOB_STALE_SECONDS: int = 900
    RESTORE_MAINTENANCE_WORK_MEM: str = "256MB"
    RESTORE_MAX_PARALLEL_MAINTENANCE_WORKERS: int = 1
    RQ_RESULT_TTL_SECONDS: int = 86_400
    RQ_FAILURE_TTL_SECONDS: int = 604_800
    APPLICATION_LOG_RETENTION_DAYS: int = 30
    SECURITY_LOG_RETENTION_DAYS: int = 90

    # Upload admission and parser containment. Valid documents inside these
    # conservative V1 limits retain the frozen processing semantics.
    PDF_MAX_FILENAME_LENGTH: int = 255
    PDF_MAX_PAGES: int = 1000
    PDF_MAX_EXTRACTED_CHARS: int = 20_000_000
    PDF_MAX_PAGE_EXTRACTED_CHARS: int = 2_000_000
    INGESTION_JOB_TIMEOUT_SECONDS: int = 1800
    PROCESSING_JOB_TIMEOUT_SECONDS: int = 3600
    INDEXING_JOB_TIMEOUT_SECONDS: int = 3600

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
    MINIO_VERSION: str = "RELEASE.2025-09-07T16-13-09Z"

    # The canonical E5 artifact is provisioned by the deployment, never
    # selected by a runtime profile. Containers mount this path explicitly.
    EMBEDDING_DEVICE: str = "cpu"
    # Hugging Face hub cache directory: directly contains models--<org>--<id>.
    # This is intentionally not the parent Hugging Face home directory.
    EMBEDDING_MODEL_CACHE_DIR: str = "/root/.cache/huggingface/hub"

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

    # Product Chat History V1. Lazy reconciliation avoids a background worker.
    CHAT_TURN_STALE_AFTER_SECONDS: int = 600
    CHAT_SESSION_PAGE_SIZE_DEFAULT: int = 30
    CHAT_SESSION_PAGE_SIZE_MAX: int = 100
    CHAT_MESSAGE_PAGE_SIZE_DEFAULT: int = 50
    CHAT_MESSAGE_PAGE_SIZE_MAX: int = 100
    CHAT_SESSION_TITLE_MAX_LENGTH: int = 100

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def resolved_deployment_profile(self) -> DeploymentProfile:
        return resolve_deployment_profile(self.DEPLOYMENT_PROFILE)

settings = Settings()
