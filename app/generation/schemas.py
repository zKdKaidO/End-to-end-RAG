from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GenerationStatus(str, Enum):
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class AnswerabilityStatus(str, Enum):
    ANSWERABLE = "ANSWERABLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class AnswerabilityValidation(str, Enum):
    PASS = "PASS"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    MISSING_STATUS = "ANSWERABILITY_STATUS_MISSING"
    MALFORMED_STATUS = "ANSWERABILITY_STATUS_MALFORMED"
    DUPLICATE_STATUS = "ANSWERABILITY_STATUS_DUPLICATE"
    UNKNOWN_STATUS = "ANSWERABILITY_STATUS_UNKNOWN"


class CitationValidation(str, Enum):
    PASS = "PASS"
    INVALID_REFERENCES = "INVALID_REFERENCES"
    MISSING_CITATIONS = "MISSING_CITATIONS"


class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_text: str
    document_ids: list[str] | None = None

    @field_validator("query_text")
    @classmethod
    def bound_query_length(cls, value: str) -> str:
        # Keep the server-owned setting authoritative at validation time
        # without creating Settings merely by importing result schemas in the
        # standalone desktop process.
        from app.core.config import settings

        if len(value) > settings.REQUEST_MAX_QUERY_CHARS:
            raise ValueError(
                f"query_text exceeds the safety limit of {settings.REQUEST_MAX_QUERY_CHARS}"
            )
        return value

    @field_validator("document_ids")
    @classmethod
    def bound_document_scope(cls, value: list[str] | None) -> list[str] | None:
        from app.core.config import settings

        if value is not None and len(value) > settings.AUTH_MAX_EXPLICIT_DOCUMENT_SCOPE:
            raise ValueError(f"document_ids exceeds the safety limit of {settings.AUTH_MAX_EXPLICIT_DOCUMENT_SCOPE}")
        return value


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    chunk_id: str
    document_id: str
    metadata_json: dict[str, Any]
    provenance_json: dict[str, Any]


class Usage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class GenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    status: GenerationStatus
    answer_text: str
    citations: list[Citation]
    invalid_citations: list[str]
    citation_validation: CitationValidation
    model_id: str
    prompt_version: str
    finish_reason: str | None
    usage: Usage | None
    answerability_status: AnswerabilityStatus | None = None
    answerability_validation: AnswerabilityValidation = AnswerabilityValidation.NOT_APPLICABLE
