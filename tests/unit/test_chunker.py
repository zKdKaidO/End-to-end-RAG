import pytest
from app.processing.chunker import Chunker
from app.processing.parser import LegalUnitData

def test_chunker():
    chunker = Chunker(max_chars=50) # Small max_chars to force splitting
    
    text = "Điều 1. Phạm vi\nĐoạn văn này rất dài và sẽ bị cắt ra. Nó có hơn năm mươi ký tự. Thêm một câu nữa để kiểm tra cắt."
    
    unit = LegalUnitData("ARTICLE", "1", "Phạm vi", 0, 4)
    unit.end_char = len(text)
    
    metadata = {
        "document_type": "Luật",
        "document_number": "01/2026/QH15"
    }
    
    chunks = chunker.generate_chunks(text, [unit], metadata)
    
    assert len(chunks) > 1
    
    # First chunk should have the correct embedding prefix
    assert "Luật 01/2026/QH15 - Điều 1" in chunks[0]["embedding_text"]
    assert "Điều 1." in chunks[0]["content_text"]
    
    # Second chunk should also have the prefix
    assert "Luật 01/2026/QH15 - Điều 1" in chunks[1]["embedding_text"]
    
    # Indices are sequential
    assert chunks[0]["chunk_index"] == 0
    assert chunks[1]["chunk_index"] == 1
