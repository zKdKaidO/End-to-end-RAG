import pytest
from app.processing.reconstruction import DocumentReconstructor

def test_document_reconstruction():
    reconstructor = DocumentReconstructor()
    
    pages = [
        "First page content.",
        "Second page content.",
        "Third page content."
    ]
    
    text, offset_map = reconstructor.reconstruct(pages)
    
    assert text == "First page content.\nSecond page content.\nThird page content."
    
    assert len(offset_map) == 3
    
    # 1. First page mapping
    assert offset_map[0]["page_number"] == 1
    assert offset_map[0]["char_start"] == 0
    assert offset_map[0]["char_end"] == len("First page content.")
    assert reconstructor.get_page_for_offset(0, offset_map) == 1
    assert reconstructor.get_page_for_offset(10, offset_map) == 1
    
    # 2. Middle page mapping
    assert offset_map[1]["page_number"] == 2
    assert offset_map[1]["char_start"] == len("First page content.\n")
    assert reconstructor.get_page_for_offset(offset_map[1]["char_start"] + 5, offset_map) == 2
    
    # 3. Last page mapping
    assert offset_map[2]["page_number"] == 3
    assert reconstructor.get_page_for_offset(offset_map[2]["char_start"] + 2, offset_map) == 3
    assert reconstructor.get_page_for_offset(len(text), offset_map) == 3
    
    # 4. Cross-page boundary mapping
    # Newline character between page 1 and 2
    boundary_offset = len("First page content.")
    assert text[boundary_offset] == "\n"
    # Actually, our offset map does not cover the \n itself technically, 
    # but our get_page_for_offset logic will assign it to the next page if it's not strictly < end.
    # Wait, end of page 1 is char_end. boundary_offset is equal to char_end of page 1.
    # So it falls into the gap, wait.
    # The gap is just 1 char. Does get_page_for_offset handle gaps?
    
def test_offset_gap_handling():
    reconstructor = DocumentReconstructor()
    pages = ["A", "B"]
    text, offset_map = reconstructor.reconstruct(pages)
    
    # offset_map:
    # 0: {char_start: 0, char_end: 1} -> "A"
    # 1: {char_start: 2, char_end: 3} -> "B"
    # Offset 1 is "\n". get_page_for_offset(1) might return -1 if not handled.
    
    assert reconstructor.get_page_for_offset(0, offset_map) == 1
    assert reconstructor.get_page_for_offset(1, offset_map) == 1
    assert reconstructor.get_page_for_offset(2, offset_map) == 2
