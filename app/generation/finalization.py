"""Pure Block 6 result finalization shared by cloud and local providers."""

from __future__ import annotations

from app.context.schemas import ContextPackage
from app.generation.answerability import parse_answerability
from app.generation.citations import validate_and_map_citations
from app.generation.profile import GenerationProfile
from app.generation.schemas import (
    AnswerabilityStatus,
    AnswerabilityValidation,
    CitationValidation,
    GenerationResult,
    GenerationStatus,
    Usage,
)


INSUFFICIENT_EVIDENCE_MESSAGE = "Bằng chứng được cung cấp không đủ để trả lời câu hỏi."


def finalize_generation_result(
    *,
    request_id: str,
    package: ContextPackage,
    profile: GenerationProfile,
    provider_text: str,
    finish_reason: str | None,
    usage: Usage | None,
    model_id: str | None = None,
) -> GenerationResult:
    """Apply the frozen answerability and citation contract without I/O."""

    parsed = parse_answerability(provider_text)
    result_model_id = model_id or profile.model_id
    if parsed.status == AnswerabilityStatus.INSUFFICIENT_EVIDENCE:
        return GenerationResult(
            request_id=request_id,
            status=GenerationStatus.INSUFFICIENT_EVIDENCE,
            answer_text=INSUFFICIENT_EVIDENCE_MESSAGE,
            citations=[],
            invalid_citations=[],
            citation_validation=CitationValidation.PASS,
            model_id=result_model_id,
            prompt_version=profile.prompt_version,
            finish_reason=finish_reason,
            usage=usage,
            answerability_status=parsed.status,
            answerability_validation=parsed.validation,
        )

    citations, invalid, validation, status = validate_and_map_citations(
        parsed.public_text, package.selected_evidence
    )
    if parsed.validation != AnswerabilityValidation.PASS:
        status = GenerationStatus.COMPLETED_WITH_WARNINGS
    return GenerationResult(
        request_id=request_id,
        status=status,
        answer_text=parsed.public_text,
        citations=citations,
        invalid_citations=invalid,
        citation_validation=validation,
        model_id=result_model_id,
        prompt_version=profile.prompt_version,
        finish_reason=finish_reason,
        usage=usage,
        answerability_status=parsed.status,
        answerability_validation=parsed.validation,
    )
