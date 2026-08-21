import pytest
from app.processing.parser import LegalParser

def test_legal_parser():
    parser = LegalParser()
    
    text = """Cộng hòa xã hội chủ nghĩa Việt Nam
    Độc lập tự do hạnh phúc
    
    Chương I
    QUY ĐỊNH CHUNG
    
    Điều 1. Phạm vi điều chỉnh
    Nghị định này quy định...
    
    1. Khoản 1 nội dung.
    a) Điểm a nội dung.
    b) Điểm b nội dung.
    
    2. Khoản 2 nội dung.
    
    Điều 2. Đối tượng
    Đối tượng là...
    
    Chương II
    TỔ CHỨC THỰC HIỆN
    """
    
    units = parser.parse(text)
    
    assert len(units) == 3 # Preamble, Chương I, Chương II
    
    preamble = units[0]
    assert preamble.unit_type == "PREAMBLE"
    
    chuong1 = units[1]
    assert chuong1.unit_type == "CHAPTER"
    assert chuong1.unit_number == "I"
    assert chuong1.title == "QUY ĐỊNH CHUNG"
    
    # Chương 1 should have Điều 1 and Điều 2
    assert len(chuong1.children) == 2
    
    dieu1 = chuong1.children[0]
    assert dieu1.unit_type == "ARTICLE"
    assert dieu1.unit_number == "1"
    assert dieu1.title == "Phạm vi điều chỉnh"
    
    # Điều 1 should have Khoản 1 and Khoản 2
    assert len(dieu1.children) == 2
    
    khoan1 = dieu1.children[0]
    assert khoan1.unit_type == "CLAUSE"
    assert khoan1.unit_number == "1"
    
    # Khoản 1 should have Điểm a and Điểm b
    assert len(khoan1.children) == 2
    assert khoan1.children[0].unit_type == "POINT"
    assert khoan1.children[0].unit_number == "a"
    
    chuong2 = units[2]
    assert chuong2.unit_type == "CHAPTER"
    assert chuong2.unit_number == "II"
