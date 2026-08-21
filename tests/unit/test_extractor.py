import pytest
import os
from app.pdf.extractor import PDFExtractor

def test_extract_pages():
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "sample_legal.pdf")
    with open(fixture_path, "rb") as f:
        pdf_bytes = f.read()
        
    pages = list(PDFExtractor.extract_pages(pdf_bytes))
    assert len(pages) == 8
    
    first_page = pages[0]
    assert first_page["page_number"] == 1
    # Vietnamese top-left header should appear properly due to sort=True
    assert "CHÍNH PHỦ" in first_page["raw_text"]
    assert first_page["char_count"] > 100
    
    last_page = pages[-1]
    assert last_page["page_number"] == 8
    assert last_page["char_count"] > 0
