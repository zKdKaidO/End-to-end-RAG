import json
import pytest
from app.processing.metadata_extractor import MetadataExtractor

def test_metadata_extraction():
    extractor = MetadataExtractor()
    
    text = """
    CHÍNH PHỦ     CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
    Độc lập - Tự do - Hạnh phúc
    
    Số: 135/2026/NĐ-CP Hà Nội, ngày 07 tháng 4 năm 2026
    
    NGHỊ ĐỊNH
    Quy định cơ chế, chính sách ưu đãi, ưu tiên cho đơn vị điều độ hệ thống điện quốc gia và đơn vị điều hành giao dịch thị trường điện
    
    Căn cứ Luật Tổ chức Chính phủ số 63/2025/QH15;
    """
    
    metadata = extractor.extract(text)
    
    assert metadata["document_type"] == "Nghị định"
    assert metadata["document_number"] == "135/2026/NĐ-CP"
    assert metadata["issuing_authority"] == "Chính phủ"
    assert metadata["issued_date"] == "2026-04-07"
    assert metadata["title"] == "Quy định cơ chế, chính sách ưu đãi, ưu tiên cho đơn vị điều độ hệ thống điện quốc gia và đơn vị điều hành giao dịch thị trường điện"
