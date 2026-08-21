import re
import unicodedata

from app.retrieval.schemas import RetrievedCandidate


_REPEATED_WHITESPACE = re.compile(r"\s+")


def normalize_content_for_dedup(content_text: str) -> str:
    normalized = unicodedata.normalize("NFC", content_text)
    return _REPEATED_WHITESPACE.sub(" ", normalized).strip()


def deduplicate_candidates(
    candidates: list[RetrievedCandidate],
) -> tuple[list[RetrievedCandidate], int]:
    """Keep the first/highest-ranked exact normalized match per document."""

    seen: set[tuple[str, str]] = set()
    kept: list[RetrievedCandidate] = []
    duplicate_count = 0

    for candidate in candidates:
        key = (
            candidate.document_id,
            normalize_content_for_dedup(candidate.content_text),
        )
        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)
        kept.append(candidate)

    return kept, duplicate_count
