from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings


class ChatSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, max_length=settings.CHAT_SESSION_TITLE_MAX_LENGTH)


class ChatSessionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=100)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be blank")
        return value


class ChatSessionSummary(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None
    last_message_preview: str | None = None
    message_count: int = 0


class ChatSessionList(BaseModel):
    data: list[ChatSessionSummary]
    next_cursor: str | None


class CitationSnapshotResponse(BaseModel):
    id: UUID
    citation_label: str
    citation_order: int
    original_document_id: UUID | None
    original_chunk_id: UUID | None
    original_legal_unit_id: UUID | None
    document_title: str | None
    document_filename: str | None
    document_sha256: str | None
    chunk_content_sha256: str
    page_start: int | None
    page_end: int | None
    article: str | None
    clause: str | None
    point: str | None
    evidence_text: str
    metadata_json: dict[str, Any]
    provenance_json: dict[str, Any]
    snapshot_version: int
    created_at: datetime
    availability: str
    current_document_id: UUID | None = None
    current_chunk_id: UUID | None = None


class ChatMessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    turn_id: UUID
    role: str
    sequence_no: int
    content: str
    delivery_state: str
    answer_status: str | None
    model_id: str | None
    prompt_version: str | None
    created_at: datetime
    finalized_at: datetime | None
    failure_code: str | None = None
    failure_detail_safe: str | None = None
    citations: list[CitationSnapshotResponse] = Field(default_factory=list)


class ChatMessagePage(BaseModel):
    data: list[ChatMessageResponse]
    next_before_sequence: int | None


class ChatTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_turn_id: UUID
    query: str = Field(min_length=1, max_length=settings.REQUEST_MAX_QUERY_CHARS)
    document_ids: list[UUID] | None = None

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value

    @field_validator("document_ids")
    @classmethod
    def deduplicate_documents(cls, value: list[UUID] | None) -> list[UUID] | None:
        if value is None:
            return None
        if len(value) > settings.AUTH_MAX_EXPLICIT_DOCUMENT_SCOPE:
            raise ValueError(f"document_ids exceeds the safety limit of {settings.AUTH_MAX_EXPLICIT_DOCUMENT_SCOPE}")
        return list(dict.fromkeys(value))
