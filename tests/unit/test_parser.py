import pytest
from app.processing.chunker import Chunker
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


def test_parser_rejects_prose_and_timestamps_that_only_look_like_headings():
    units = LegalParser().parse(
        "Chương III\nQUY ĐỊNH\nĐiều 11. Hình thức cập nhật.\n"
        "Chương trình, tài liệu đào tạo không phải là một chương.\n"
        "Phần l — ý thuyết: 17:03:43\n"
        "1. Khoản hợp lệ.\n"
    )

    chapter = next(item for item in units if item.unit_type == "CHAPTER")
    assert chapter.unit_number == "III"
    assert all(item.unit_type != "PART" for item in units)
    article = next(item for item in chapter.children if item.unit_type == "ARTICLE")
    assert article.unit_number == "11"
    assert article.children[0].unit_type == "CLAUSE"


def test_parser_recovers_monotonic_article_after_pdf_footer_noise():
    units = LegalParser().parse(
        "Điều 11. Hình thức nghiên cứu.\n1. Nội dung. footer Điều 12. Hình thức tự cập nhật.\n1. Nội dung khác."
    )
    articles = [item for item in units if item.unit_type == "ARTICLE"]
    assert [item.unit_number for item in articles] == ["11", "12"]


def test_parser_recognizes_appendix_table_categories_without_treating_prose_as_part():
    units = LegalParser().parse(
        "PHỤ LỤC 04\nBẢNG QUY ĐỔI\n1 Tham gia đào tạo\n"
        "1 tiết học = 1 giờ tín chỉ\n2 Biên soạn tài liệu\n"
        "3 Nghiên cứu khoa học\n4 Tự cập nhật kiến thức\n"
    )
    appendix = next(item for item in units if item.unit_type == "APPENDIX")
    assert appendix.unit_number == "04"
    assert [(item.unit_type, item.unit_number) for item in appendix.children] == [
        ("TABLE_CATEGORY", "1"), ("TABLE_CATEGORY", "2"),
        ("TABLE_CATEGORY", "3"), ("TABLE_CATEGORY", "4"),
    ]


def test_appendix_neighboring_categories_are_distinct_authoritative_chunks():
    class _AlwaysFits:
        def fits(self, text):
            return True

        def validate(self, chunk_id, text):
            return None

    text = (
        "PHỤ LỤC 04\n1 Hoạt động đào tạo\nNội dung riêng của hoạt động đào tạo.\n"
        "2 Hoạt động biên soạn\nNội dung riêng của hoạt động biên soạn.\n"
    )
    chunks = Chunker(input_contract=_AlwaysFits()).generate_chunks(
        text,
        LegalParser().parse(text),
        {},
    )
    categories = {
        chunk["legal_unit"].unit_number: chunk["content_text"]
        for chunk in chunks
        if chunk["legal_unit"].unit_type == "TABLE_CATEGORY"
    }

    assert set(categories) == {"1", "2"}
    assert "biên soạn" not in categories["1"]
    assert "đào tạo" not in categories["2"]
