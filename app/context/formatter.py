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
    hierarchy = _format_authoritative_hierarchy(candidate)
    category_key = _format_authoritative_category_key(candidate)
    relation = _format_hierarchy_relation(candidate)
    location = ""
    if hierarchy or relation:
        parts = ["Vị trí pháp lý:"]
        if hierarchy:
            parts.extend(hierarchy)
        if category_key:
            parts.append(f"Mã danh mục pháp lý được phép: {category_key}")
        if relation:
            parts.append(f"Quan hệ: {relation}")
        location = "\n" + "\n".join(parts) + "\n"
    return (
        f"[Evidence {source_id}]\n"
        f"Nguồn: {identity}\n"
        f"{location}\n"
        f"Nội dung:\n"
        f"{candidate.content_text}"
    )


def authoritative_group_key(candidate: RetrievedCandidate, source_id: str) -> tuple[str, str]:
    """Use the deepest resolved unit; unresolved evidence never coalesces."""
    resolved = candidate.metadata_json.get("authoritative_legal_path")
    if not isinstance(resolved, dict) or resolved.get("path_source") not in {
        "LEGAL_UNIT_REPOSITORY", "REPAIRED_LEGAL_UNIT_REPOSITORY"
    }:
        return ("UNAVAILABLE", source_id)
    unit_id = resolved.get("legal_unit_id")
    if not isinstance(unit_id, str) or not unit_id:
        return ("UNAVAILABLE", source_id)
    return (candidate.document_id, unit_id)


def format_grouped_evidence(
    evidence: list[tuple[RetrievedCandidate, str]],
) -> str:
    """Group same-unit evidence while keeping every source individually citable."""
    groups: list[tuple[tuple[str, str], list[tuple[RetrievedCandidate, str]]]] = []
    positions: dict[tuple[str, str], int] = {}
    for candidate, source_id in evidence:
        key = authoritative_group_key(candidate, source_id)
        if key not in positions:
            positions[key] = len(groups)
            groups.append((key, []))
        groups[positions[key]][1].append((candidate, source_id))

    output: list[str] = []
    for number, (_key, items) in enumerate(groups, start=1):
        candidate = items[0][0]
        path = _format_authoritative_hierarchy(candidate)
        if len(items) > 1 and path:
            output.append(
                f"[Legal Group G{number}]\nVị trí pháp lý:\n"
                + "\n".join(path)
                + (
                    f"\nMã danh mục pháp lý được phép: {_format_authoritative_category_key(candidate)}"
                    if _format_authoritative_category_key(candidate)
                    else ""
                )
            )
            bodies = [_format_evidence_body(item, source_id) for item, source_id in items]
            output.append(EVIDENCE_SEPARATOR.join(bodies))
        else:
            output.append(
                EVIDENCE_SEPARATOR.join(
                    format_evidence_block(item, source_id) for item, source_id in items
                )
            )
    return EVIDENCE_SEPARATOR.join(output)


def _format_evidence_body(candidate: RetrievedCandidate, source_id: str) -> str:
    return (
        f"[Evidence {source_id}]\n"
        f"Nguồn: {format_legal_identity(candidate.metadata_json)}\n\n"
        f"Nội dung:\n{candidate.content_text}"
    )


def _format_authoritative_hierarchy(candidate: RetrievedCandidate) -> list[str]:
    """Render the resolver contract, never arbitrary chunk metadata."""
    resolved = candidate.metadata_json.get("authoritative_legal_path")
    if not isinstance(resolved, dict):
        return []
    if resolved.get("path_source") not in {
        "LEGAL_UNIT_REPOSITORY", "REPAIRED_LEGAL_UNIT_REPOSITORY"
    }:
        return []
    path = resolved.get("ancestor_display_labels")
    if not isinstance(path, list) or not all(isinstance(part, str) and part.strip() for part in path):
        return []
    return [part.strip() for part in path]


def _format_authoritative_category_key(candidate: RetrievedCandidate) -> str | None:
    resolved = candidate.metadata_json.get("authoritative_legal_path")
    if not isinstance(resolved, dict):
        return None
    if resolved.get("path_source") not in {
        "LEGAL_UNIT_REPOSITORY", "REPAIRED_LEGAL_UNIT_REPOSITORY"
    }:
        return None
    category_key = resolved.get("category_key")
    return category_key if isinstance(category_key, str) and category_key else None


def _format_hierarchy_relation(candidate: RetrievedCandidate) -> str | None:
    if candidate.candidate_origin.value == "HIERARCHY_CHILD":
        return "Nội dung con trực tiếp của căn cứ được truy xuất"
    if candidate.candidate_origin.value == "RETRIEVAL":
        return "Căn cứ được truy xuất trực tiếp"
    return None
