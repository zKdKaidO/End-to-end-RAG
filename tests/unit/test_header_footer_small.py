import pytest
from app.processing.header_footer import HeaderFooterRemover

def test_header_footer_small_document_safety():
    remover = HeaderFooterRemover(check_lines=3, frequency_threshold=0.5)
    
    pages = [
        "CHƯƠNG I\nQuy định chung\nNội dung chương 1",
        "CHƯƠNG II\nTổ chức\nNội dung chương 2"
    ]
    
    # In a 2-page document, "chương i" appears once (1/2 = 0.5), "chương ii" appears once (1/2 = 0.5).
    # If the threshold is 0.5 and it doesn't require count > 1, it would remove BOTH!
    # Our fix requires count > 1, so it shouldn't remove anything.
    cleaned = remover.remove_headers_footers(pages)
    
    assert "CHƯƠNG I" in cleaned[0]
    assert "CHƯƠNG II" in cleaned[1]
