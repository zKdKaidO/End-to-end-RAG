from typing import Tuple
from app.core.exceptions import InvalidDocumentError
from app.core.logging import get_logger
from app.core.config import settings
from app.pdf.admission import validate_pdf_admission

logger = get_logger(__name__)

def validate_and_hash_pdf(file_bytes: bytes, filename: str, mime_type: str) -> Tuple[bytes, str]:
    """Validates the PDF bytes and calculates SHA-256."""
    try:
        return validate_pdf_admission(
            file_bytes,
            filename,
            mime_type,
            max_bytes=settings.MAX_UPLOAD_SIZE,
            max_filename_length=settings.PDF_MAX_FILENAME_LENGTH,
            max_pages=settings.PDF_MAX_PAGES,
        )
    except InvalidDocumentError as exc:
        if file_bytes and not file_bytes.startswith(b"%PDF-"):
            # Retain the server's existing structured diagnostic, without
            # leaking any source document content.
            logger.warning("invalid_pdf_magic_number", filename=filename)
        raise
