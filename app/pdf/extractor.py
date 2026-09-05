import pymupdf
from typing import Iterator, Dict, Any

from app.core.exceptions import InvalidDocumentError


_UNSET = object()


class PDFExtractor:
    @staticmethod
    def extract_pages(
        pdf_bytes: bytes,
        *,
        max_pages: int | None | object = _UNSET,
        max_page_extracted_chars: int | object = _UNSET,
        max_extracted_chars: int | object = _UNSET,
    ) -> Iterator[Dict[str, Any]]:
        """
        Extracts pages from a PDF.
        Yields dict with page_number, raw_text, char_count.
        """
        if (
            max_pages is _UNSET
            or max_page_extracted_chars is _UNSET
            or max_extracted_chars is _UNSET
        ):
            # Preserve the production API's configured limits while allowing
            # the desktop runtime to pass its own explicit local policy.
            from app.core.config import settings

            max_pages = settings.PDF_MAX_PAGES if max_pages is _UNSET else max_pages
            max_page_extracted_chars = (
                settings.PDF_MAX_PAGE_EXTRACTED_CHARS
                if max_page_extracted_chars is _UNSET
                else max_page_extracted_chars
            )
            max_extracted_chars = (
                settings.PDF_MAX_EXTRACTED_CHARS
                if max_extracted_chars is _UNSET
                else max_extracted_chars
            )

        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        total_chars = 0
        try:
            if doc.needs_pass or (max_pages is not None and doc.page_count > max_pages):
                raise InvalidDocumentError("PDF violates configured parser limits.")
            for i, page in enumerate(doc):
                # sort=True provides natural top-to-bottom reading order
                text = page.get_text("text", sort=True)
                if len(text) > max_page_extracted_chars:
                    raise InvalidDocumentError("PDF page exceeds the extracted-text safety limit.")
                total_chars += len(text)
                if total_chars > max_extracted_chars:
                    raise InvalidDocumentError("PDF exceeds the total extracted-text safety limit.")
                yield {
                    "page_number": i + 1,
                    "raw_text": text,
                    "char_count": len(text)
                }
        finally:
            doc.close()
