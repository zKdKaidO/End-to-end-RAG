"""Dependency-free PDF admission primitive shared by server and local Compute."""

from __future__ import annotations

import hashlib
import unicodedata
from typing import Tuple

import pymupdf

from app.core.exceptions import InvalidDocumentError


def validate_pdf_admission(
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    *,
    max_bytes: int,
    max_filename_length: int,
    max_pages: int | None,
) -> Tuple[bytes, str]:
    """Validate source-PDF bytes without application configuration/logging.

    ``max_pages=None`` is used only by the local product contract, which has
    no arbitrary page-count limit. All structural and encrypted-PDF checks
    remain mandatory in both callers.
    """
    if not file_bytes:
        raise InvalidDocumentError("PDF file must not be empty.")
    if len(file_bytes) > max_bytes:
        raise InvalidDocumentError(f"File size exceeds limit of {max_bytes} bytes.")
    if not file_bytes.startswith(b"%PDF-"):
        raise InvalidDocumentError("Invalid PDF format. Magic number mismatch.")

    normalized_filename = unicodedata.normalize("NFC", filename)
    if (
        not normalized_filename
        or len(normalized_filename) > max_filename_length
        or "\x00" in normalized_filename
        or "/" in normalized_filename
        or "\\" in normalized_filename
        or not normalized_filename.casefold().endswith(".pdf")
    ):
        raise InvalidDocumentError("Invalid PDF filename.")
    if mime_type.casefold() != "application/pdf":
        raise InvalidDocumentError("Invalid PDF content type.")

    try:
        document = pymupdf.open(stream=file_bytes, filetype="pdf")
        try:
            if not document.is_pdf or document.needs_pass:
                raise InvalidDocumentError("Encrypted or password-protected PDFs are not supported.")
            if document.page_count <= 0:
                raise InvalidDocumentError("PDF must contain at least one page.")
            if max_pages is not None and document.page_count > max_pages:
                raise InvalidDocumentError(f"PDF page count exceeds the limit of {max_pages} pages.")
        finally:
            document.close()
    except InvalidDocumentError:
        raise
    except Exception as exc:
        raise InvalidDocumentError("Malformed or truncated PDF.") from exc

    return file_bytes, hashlib.sha256(file_bytes).hexdigest()
