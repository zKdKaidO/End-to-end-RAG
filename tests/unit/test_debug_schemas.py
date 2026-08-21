import pytest
from pydantic import ValidationError

from app.debug.schemas import DebugRagRequest, EvaluationDiagnosis, LexicalMode


def test_debug_request_is_strict_and_has_no_production_overrides():
    request = DebugRagRequest(
        query_text="  Doanh nghiệp được hưởng ưu đãi gì?  ",
        document_ids=None,
        evaluation_case_id="scope_direct",
    )
    assert request.query_text == "Doanh nghiệp được hưởng ưu đãi gì?"
    assert set(request.model_fields_set) == {
        "query_text",
        "document_ids",
        "evaluation_case_id",
    }
    for forbidden in ("model", "temperature", "top_k", "system_prompt", "rrf_k"):
        with pytest.raises(ValidationError):
            DebugRagRequest.model_validate({"query_text": "q", forbidden: 1})


@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
def test_debug_request_rejects_empty_query(query):
    with pytest.raises(ValidationError):
        DebugRagRequest(query_text=query)


def test_controlled_debug_enums_are_stable():
    assert {item.value for item in LexicalMode} == {
        "STRICT_MATCH",
        "SELECTIVE_FALLBACK",
        "NO_LEXICAL_MATCH",
    }
    assert "FALSE_ABSTENTION" in {item.value for item in EvaluationDiagnosis}

