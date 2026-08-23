import pymupdf
from typing import Iterator, Dict, Any

from app.core.config import settings
from app.core.exceptions import InvalidDocumentError

class PDFExtractor:
    @staticmethod
    def extract_pages(pdf_bytes: bytes) -> Iterator[Dict[str, Any]]:
        """
        Extracts pages from a PDF.
        Yields dict with page_number, raw_text, char_count.
        """
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        total_chars = 0
        try:
            if doc.needs_pass or doc.page_count > settings.PDF_MAX_PAGES:
                raise InvalidDocumentError("PDF violates configured parser limits.")
            for i, page in enumerate(doc):
                # sort=True provides natural top-to-bottom reading order
                text = page.get_text("text", sort=True)
                if len(text) > settings.PDF_MAX_PAGE_EXTRACTED_CHARS:
                    raise InvalidDocumentError("PDF page exceeds the extracted-text safety limit.")
                total_chars += len(text)
                if total_chars > settings.PDF_MAX_EXTRACTED_CHARS:
                    raise InvalidDocumentError("PDF exceeds the total extracted-text safety limit.")
                yield {
                    "page_number": i + 1,
                    "raw_text": text,
                    "char_count": len(text)
                }
        finally:
            doc.close()
