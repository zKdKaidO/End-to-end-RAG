from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvaluationCategory(str, Enum):
    DIRECT_FACT = "DIRECT_FACT"
    SEMANTIC_PARAPHRASE = "SEMANTIC_PARAPHRASE"
    KEYWORD_IDENTIFIER = "KEYWORD_IDENTIFIER"
    DEEPER_RANK = "DEEPER_RANK"
    MULTI_EVIDENCE = "MULTI_EVIDENCE"
    DOCUMENT_FILTER = "DOCUMENT_FILTER"
    UNANSWERABLE = "UNANSWERABLE"
    OUT_OF_CORPUS = "OUT_OF_CORPUS"
    MULTI_DOCUMENT_EVIDENCE = "MULTI_DOCUMENT_EVIDENCE"
    CROSS_DOCUMENT = "CROSS_DOCUMENT"
    SAME_TERM_DIFFERENT_DOCUMENT = "SAME_TERM_DIFFERENT_DOCUMENT"
    SAME_ARTICLE_NUMBER = "SAME_ARTICLE_NUMBER"
    DOCUMENT_DISAMBIGUATION = "DOCUMENT_DISAMBIGUATION"
    NEAR_DUPLICATE_EVIDENCE = "NEAR_DUPLICATE_EVIDENCE"
    PARTIAL_SUPPORT = "PARTIAL_SUPPORT"
    AMBIGUOUS_QUERY = "AMBIGUOUS_QUERY"
    HARD_UNANSWERABLE = "HARD_UNANSWERABLE"


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    category: EvaluationCategory
    question: str = Field(min_length=1)
    answerable: bool
    document_ids: list[str] | None = None
    expected_document_ids: list[str] = Field(default_factory=list)
    acceptable_evidence_sets: list[list[str]] = Field(default_factory=list)
    source_reference: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_answerability_contract(self):
        if self.answerable:
            if not self.expected_document_ids:
                raise ValueError("answerable cases require expected_document_ids")
            if not self.acceptable_evidence_sets or any(not item for item in self.acceptable_evidence_sets):
                raise ValueError("answerable cases require non-empty acceptable_evidence_sets")
            if not self.source_reference or not self.source_reference.strip():
                raise ValueError("answerable cases require source_reference")
        elif self.expected_document_ids or self.acceptable_evidence_sets:
            raise ValueError("unanswerable cases must not declare expected evidence")
        return self


class EvaluationDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    description: str
    cases: list[EvaluationCase] = Field(min_length=1)


class FailureAttribution(str, Enum):
    RETRIEVAL_MISS = "RETRIEVAL_MISS"
    CONTEXT_DROP = "CONTEXT_DROP"
    GENERATION_MISSING_CITATION = "GENERATION_MISSING_CITATION"
    GENERATION_INVALID_CITATION = "GENERATION_INVALID_CITATION"
    GENERATION_WRONG_SOURCE = "GENERATION_WRONG_SOURCE"
    UNSUPPORTED_ANSWER = "UNSUPPORTED_ANSWER"
    INSUFFICIENT_EVIDENCE_FALSE_NEGATIVE = "INSUFFICIENT_EVIDENCE_FALSE_NEGATIVE"
    OTHER = "OTHER"
    MULTIPLE_AMBIGUOUS = "MULTIPLE_AMBIGUOUS"
