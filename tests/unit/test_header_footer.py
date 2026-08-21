import pytest
from app.processing.header_footer import HeaderFooterRemover

def test_header_footer_removal():
    remover = HeaderFooterRemover(check_lines=3, frequency_threshold=0.5)
    
    pages = [
        "VĂN BẢN QUY PHẠM PHÁP LUẬT\n1\nĐiều 1. Phạm vi\nNội dung 1\nFOOTER TEXT",
        "VĂN BẢN QUY PHẠM PHÁP LUẬT\n2\nNội dung 2\nTiếp tục nội dung\nFOOTER TEXT",
        "VĂN BẢN QUY PHẠM PHÁP LUẬT\nTrang 3\nĐiều 2. Quy định\nNội dung 3\nFOOTER TEXT"
    ]
    
    cleaned = remover.remove_headers_footers(pages)
    
    assert "VĂN BẢN QUY PHẠM PHÁP LUẬT" not in cleaned[0]
    assert "FOOTER TEXT" not in cleaned[0]
    assert "Điều 1. Phạm vi" in cleaned[0]
    
    assert not cleaned[1].startswith("2\n")
    assert "Nội dung 2" in cleaned[1]
    
    assert "Trang 3" not in cleaned[2]
    assert "Điều 2. Quy định" in cleaned[2]
    
def test_no_blind_removal():
    remover = HeaderFooterRemover(check_lines=3, frequency_threshold=0.5)
    
    # Text that shouldn't be removed because it's not repeated
    pages = [
        "Điều 1. Khái niệm\nNội dung điều 1\nKết thúc khoản 1",
        "Điều 2. Chức năng\nNội dung điều 2\nKết thúc khoản 2",
        "Điều 3. Nhiệm vụ\nNội dung điều 3\nKết thúc khoản 3"
    ]
    
    cleaned = remover.remove_headers_footers(pages)
    
    assert "Điều 1. Khái niệm" in cleaned[0]
    assert "Kết thúc khoản 1" in cleaned[0]
    assert "Điều 3. Nhiệm vụ" in cleaned[2]
