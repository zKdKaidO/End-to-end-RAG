import pytest

from app.generation.answerability import parse_answerability
from app.generation.schemas import AnswerabilityStatus, AnswerabilityValidation


@pytest.mark.parametrize(
    "provider_text,status,public_text",
    [
        ("[STATUS: ANSWERABLE]\nTrả lời [S1]", AnswerabilityStatus.ANSWERABLE, "Trả lời [S1]"),
        ("  \n[STATUS :  ANSWERABLE ]\r\nTrả lời", AnswerabilityStatus.ANSWERABLE, "Trả lời"),
        ("[STATUS: INSUFFICIENT_EVIDENCE]", AnswerabilityStatus.INSUFFICIENT_EVIDENCE, ""),
    ],
)
def test_valid_answerability_markers(provider_text, status, public_text):
    parsed = parse_answerability(provider_text)
    assert parsed.status == status
    assert parsed.validation == AnswerabilityValidation.PASS
    assert parsed.public_text == public_text
    assert "[STATUS" not in parsed.public_text


@pytest.mark.parametrize(
    "provider_text,validation",
    [
        ("Bằng chứng không đủ thông tin.", AnswerabilityValidation.MISSING_STATUS),
        ("[STATUS ANSWERABLE]\nTrả lời", AnswerabilityValidation.MALFORMED_STATUS),
        ("[STATUS: ANSWERABLE\nTrả lời", AnswerabilityValidation.MALFORMED_STATUS),
        ("[STATUS: MAYBE]\nTrả lời", AnswerabilityValidation.UNKNOWN_STATUS),
        ("[status: answerable]\nTrả lời", AnswerabilityValidation.MALFORMED_STATUS),
        ("[STATUS: ANSWERABLE]\nTrả lời\n[STATUS: ANSWERABLE]", AnswerabilityValidation.DUPLICATE_STATUS),
    ],
)
def test_invalid_answerability_markers_never_guess_from_free_text(provider_text, validation):
    parsed = parse_answerability(provider_text)
    assert parsed.status is None
    assert parsed.validation == validation
    assert "[STATUS" not in parsed.public_text.upper()
