import re
import unicodedata
from typing import Any

from app.retrieval.schemas import RetrievedCandidate


EVIDENCE_SEPARATOR = "\n\n---\n\n"
MISSING_LEGAL_IDENTITY = "Không có thông tin định danh trong metadata"
_WHITESPACE = re.compile(r"\s+")


def _metadata_text(metadata: dict[str, Any], field: str) -> str | None:
    value = metadata.get(field)
    if not isinstance(value, str):
        return None
    cleaned = _WHITESPACE.sub(" ", unicodedata.normalize("NFC", value)).strip()
    return cleaned or None


def format_legal_identity(metadata: dict[str, Any]) -> str:
    document_type = _metadata_text(metadata, "document_type")
    document_number = _metadata_text(metadata, "document_number")
    title = _metadata_text(metadata, "title")

    identity_parts: list[str] = []
    if document_type and document_number:
        identity_parts.append(f"{document_type} số {document_number}")
    elif document_type:
        identity_parts.append(document_type)
    elif document_number:
        identity_parts.append(f"Số {document_number}")

    if title:
        identity_parts.append(title)

    return " — ".join(identity_parts) if identity_parts else MISSING_LEGAL_IDENTITY


def format_evidence_block(candidate: RetrievedCandidate, source_id: str) -> str:
    identity = format_legal_identity(candidate.metadata_json)
    return (
        f"[Evidence {source_id}]\n"
        f"Nguồn: {identity}\n\n"
        f"Nội dung:\n"
        f"{candidate.content_text}"
    )
