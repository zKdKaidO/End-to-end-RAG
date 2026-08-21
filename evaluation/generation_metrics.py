from collections.abc import Sequence

from evaluation.context_metrics import evidence_solution_present
from evaluation.schemas import FailureAttribution


def expected_source_match(
    mapped_citation_chunk_ids: Sequence[str], acceptable_evidence_sets: Sequence[Sequence[str]]
) -> bool:
    return evidence_solution_present(mapped_citation_chunk_ids, acceptable_evidence_sets)


def classify_failure(
    *,
    answerable: bool,
    retrieval_found: bool,
    context_retained: bool,
    status: str,
    answer_text: str,
    citation_validation: str,
    expected_citation_match: bool | None,
) -> FailureAttribution | None:
    if not answerable:
        if status == "INSUFFICIENT_EVIDENCE":
            return None
        if answer_text.strip():
            return FailureAttribution.UNSUPPORTED_ANSWER
        return FailureAttribution.OTHER
    if not retrieval_found:
        return FailureAttribution.RETRIEVAL_MISS
    if not context_retained:
        return FailureAttribution.CONTEXT_DROP
    if status == "INSUFFICIENT_EVIDENCE":
        return FailureAttribution.INSUFFICIENT_EVIDENCE_FALSE_NEGATIVE
    if citation_validation == "INVALID_REFERENCES":
        return FailureAttribution.GENERATION_INVALID_CITATION
    if citation_validation == "MISSING_CITATIONS":
        return FailureAttribution.GENERATION_MISSING_CITATION
    if expected_citation_match is False:
        return FailureAttribution.GENERATION_WRONG_SOURCE
    return None


def unsupported_answer(answerable: bool, status: str, answer_text: str) -> bool:
    return not answerable and status != "INSUFFICIENT_EVIDENCE" and bool(answer_text.strip())
