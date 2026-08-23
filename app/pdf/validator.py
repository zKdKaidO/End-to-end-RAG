import hashlib
import unicodedata
from typing import Tuple
import pymupdf
from app.core.exceptions import InvalidDocumentError
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)

def validate_and_hash_pdf(file_bytes: bytes, filename: str, mime_type: str) -> Tuple[bytes, str]:
    """Validates the PDF bytes and calculates SHA-256."""
    
    # 1. Size Validation
    if not file_bytes:
        raise InvalidDocumentError("PDF file must not be empty.")
    if len(file_bytes) > settings.MAX_UPLOAD_SIZE:
        raise InvalidDocumentError(f"File size exceeds limit of {settings.MAX_UPLOAD_SIZE} bytes.")
        
    # 2. Magic Number Validation
    if not file_bytes.startswith(b"%PDF-"):
        logger.warning("invalid_pdf_magic_number", filename=filename)
        raise InvalidDocumentError("Invalid PDF format. Magic number mismatch.")

    normalized_filename = unicodedata.normalize("NFC", filename)
    if (
        not normalized_filename
        or len(normalized_filename) > settings.PDF_MAX_FILENAME_LENGTH
        or "\x00" in normalized_filename
        or "/" in normalized_filename
        or "\\" in normalized_filename
        or not normalized_filename.casefold().endswith(".pdf")
    ):
        raise InvalidDocumentError("Invalid PDF filename.")
    if mime_type.casefold() != "application/pdf":
        raise InvalidDocumentError("Invalid PDF content type.")

    # 3. Structural admission. Content extraction remains in the contained
    # ingestion worker and retains the frozen legal-processing semantics.
    try:
        document = pymupdf.open(stream=file_bytes, filetype="pdf")
        try:
            if not document.is_pdf or document.needs_pass:
                raise InvalidDocumentError("Encrypted or password-protected PDFs are not supported.")
            page_count = document.page_count
            if page_count <= 0:
                raise InvalidDocumentError("PDF must contain at least one page.")
            if page_count > settings.PDF_MAX_PAGES:
                raise InvalidDocumentError(f"PDF page count exceeds the limit of {settings.PDF_MAX_PAGES} pages.")
        finally:
            document.close()
    except InvalidDocumentError:
        raise
    except Exception as exc:
        raise InvalidDocumentError("Malformed or truncated PDF.") from exc
        
    # 4. Calculate SHA-256
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()
    
    return file_bytes, sha256_hash
