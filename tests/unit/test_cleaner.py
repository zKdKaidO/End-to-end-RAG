import pytest
from app.processing.cleaner import PageCleaner

def test_page_cleaner():
    cleaner = PageCleaner()
    
    # 1. Unicode NFC
    # "Tiếng Việt" with decomposed characters
    decomposed = "Ti\u00ea\u0301ng Vi\u00ea\u0323t"
    cleaned = cleaner.clean(decomposed)
    assert cleaned == "Tiếng Việt"
    
    # 2. Line endings & trailing whitespace
    text = "Line 1 \r\nLine 2  \rLine 3\t \n"
    cleaned = cleaner.clean(text)
    assert cleaned == "Line 1\nLine 2\nLine 3\n"
    
    # 3. Collapse multiple spaces
    text = "    CHÍNH PHỦ     CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM  "
    cleaned = cleaner.clean(text)
    assert cleaned == "CHÍNH PHỦ CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM"
    
    # 4. Multiple newlines
    text = "Paragraph 1\n\n\n\nParagraph 2"
    cleaned = cleaner.clean(text)
    assert cleaned == "Paragraph 1\n\nParagraph 2"
    
    # 5. Preserve legal numbering
    text = "Điều 1. Phạm vi điều chỉnh\n\n1. Nghị định này..."
    cleaned = cleaner.clean(text)
    assert "Điều 1." in cleaned
    assert "1. Nghị định" in cleaned
