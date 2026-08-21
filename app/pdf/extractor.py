import pymupdf
from typing import Iterator, Dict, Any

class PDFExtractor:
    @staticmethod
    def extract_pages(pdf_bytes: bytes) -> Iterator[Dict[str, Any]]:
        """
        Extracts pages from a PDF.
        Yields dict with page_number, raw_text, char_count.
        """
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        for i, page in enumerate(doc):
            # sort=True provides natural top-to-bottom reading order
            text = page.get_text("text", sort=True)
            yield {
                "page_number": i + 1,
                "raw_text": text,
                "char_count": len(text)
            }
        doc.close()
