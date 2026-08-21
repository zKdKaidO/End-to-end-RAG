import hashlib
from typing import Tuple
from fastapi import UploadFile
from app.core.exceptions import InvalidDocumentError
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)

def validate_and_hash_pdf(file_bytes: bytes, filename: str, mime_type: str) -> Tuple[bytes, str]:
    """Validates the PDF bytes and calculates SHA-256."""
    
    # 1. Size Validation
    if len(file_bytes) > settings.MAX_UPLOAD_SIZE:
        raise InvalidDocumentError(f"File size exceeds limit of {settings.MAX_UPLOAD_SIZE} bytes.")
        
    # 2. Magic Number Validation
    if not file_bytes.startswith(b"%PDF-"):
        logger.warning("invalid_pdf_magic_number", filename=filename)
        raise InvalidDocumentError("Invalid PDF format. Magic number mismatch.")
        
    # 3. Calculate SHA-256
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()
    
    return file_bytes, sha256_hash
