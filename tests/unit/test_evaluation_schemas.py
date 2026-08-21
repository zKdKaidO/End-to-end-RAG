import pytest
from pydantic import ValidationError

from evaluation.schemas import EvaluationCase


def test_answerable_case_requires_real_ground_truth_fields():
    with pytest.raises(ValidationError):
        EvaluationCase(case_id="a", category="DIRECT_FACT", question="q", answerable=True)


def test_unanswerable_case_rejects_expected_evidence():
    with pytest.raises(ValidationError):
        EvaluationCase(
            case_id="u", category="UNANSWERABLE", question="q", answerable=False,
            expected_document_ids=["doc"], acceptable_evidence_sets=[["chunk"]],
        )


def test_unknown_category_and_extra_fields_are_rejected():
    with pytest.raises(ValidationError):
        EvaluationCase(case_id="a", category="UNKNOWN", question="q", answerable=False)
    with pytest.raises(ValidationError):
        EvaluationCase(case_id="a", category="UNANSWERABLE", question="q", answerable=False, threshold=1)
