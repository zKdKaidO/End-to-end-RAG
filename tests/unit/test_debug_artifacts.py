from app.debug.schemas import EvaluationDiagnosis
from app.debug.services import (
    FROZEN_DATASET_SHA256,
    EvaluationArtifactService,
    assert_frozen_dataset,
)


def test_frozen_artifacts_are_typed_and_loaded_from_json():
    service = EvaluationArtifactService()
    summary = service.summary()
    cases = service.cases()
    comparison = service.comparison()

    assert assert_frozen_dataset() == FROZEN_DATASET_SHA256
    assert summary.aggregate["case_count"] == 32
    assert len(cases) == 32
    assert any(case.diagnosis == EvaluationDiagnosis.FALSE_ABSTENTION for case in cases)
    assert comparison.before["retrieval"]["hit_at_1"] == comparison.after["retrieval"]["hit_at_1"]
    assert comparison.delta["generation"]["missing_citation_rate"] < 0


def test_evaluation_case_detail_preserves_ground_truth():
    service = EvaluationArtifactService()
    detail = service.case_detail("scope_direct")
    assert detail.dataset_case["case_id"] == "scope_direct"
    assert detail.dataset_case["acceptable_evidence_sets"]
    assert detail.measured_case["case_id"] == "scope_direct"

