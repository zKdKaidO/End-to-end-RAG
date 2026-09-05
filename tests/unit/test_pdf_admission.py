from __future__ import annotations

import hashlib

import pymupdf
import pytest

from app.core.exceptions import InvalidDocumentError
from app.pdf.admission import validate_pdf_admission


def _pdf_bytes(text: str = "Legal source") -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    payload = document.tobytes()
    document.close()
    return payload


def test_dependency_light_pdf_admission_accepts_and_hashes_valid_pdf():
    payload = _pdf_bytes()
    returned, digest = validate_pdf_admission(
        payload,
        "hợp-lệ.pdf",
        "application/pdf",
        max_bytes=len(payload),
        max_filename_length=255,
        max_pages=1,
    )
    assert returned == payload
    assert digest == hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize(
    ("payload", "filename", "mime_type"),
    [
        (b"not-a-pdf", "legal.pdf", "application/pdf"),
        (_pdf_bytes(), "../legal.pdf", "application/pdf"),
        (_pdf_bytes(), "legal.pdf", "text/plain"),
    ],
)
def test_dependency_light_pdf_admission_retains_security_rejections(
    payload,
    filename,
    mime_type,
):
    with pytest.raises(InvalidDocumentError):
        validate_pdf_admission(
            payload,
            filename,
            mime_type,
            max_bytes=10 * 1024 * 1024,
            max_filename_length=255,
            max_pages=1000,
        )
