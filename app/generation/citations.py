import re

from app.context.schemas import SelectedEvidence
from app.generation.schemas import Citation, CitationValidation, GenerationStatus


_CITATION_PATTERN = re.compile(r"\[S([1-9][0-9]*)\]")


def parse_citation_ids(answer_text: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _CITATION_PATTERN.finditer(answer_text):
        source_id = f"S{match.group(1)}"
        if source_id not in seen:
            seen.add(source_id)
            ordered.append(source_id)
    return ordered


def validate_and_map_citations(
    answer_text: str,
    selected_evidence: list[SelectedEvidence],
) -> tuple[list[Citation], list[str], CitationValidation, GenerationStatus]:
    available = {item.source_id: item for item in selected_evidence}
    parsed = parse_citation_ids(answer_text)
    valid_ids = [source_id for source_id in parsed if source_id in available]
    invalid_ids = [source_id for source_id in parsed if source_id not in available]
    citations = [
        Citation(
            source_id=source_id,
            chunk_id=available[source_id].chunk_id,
            document_id=available[source_id].document_id,
            metadata_json=available[source_id].metadata_json,
            provenance_json=available[source_id].provenance_json,
        )
        for source_id in valid_ids
    ]
    if invalid_ids:
        return citations, invalid_ids, CitationValidation.INVALID_REFERENCES, GenerationStatus.COMPLETED_WITH_WARNINGS
    if answer_text.strip() and not valid_ids:
        return [], [], CitationValidation.MISSING_CITATIONS, GenerationStatus.COMPLETED_WITH_WARNINGS
    return citations, [], CitationValidation.PASS, GenerationStatus.COMPLETED
