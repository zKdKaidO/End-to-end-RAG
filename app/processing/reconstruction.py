from typing import List, Dict, Any, Tuple

class DocumentReconstructor:
    def reconstruct(self, pages: List[str]) -> Tuple[str, List[Dict[str, Any]]]:
        normalized_text = ""
        page_offset_map = []
        
        current_offset = 0
        for i, page_text in enumerate(pages):
            page_number = i + 1
            if not page_text:
                continue
                
            if normalized_text:
                # Join pages with a newline to maintain spacing/paragraph structure
                normalized_text += "\n"
                current_offset += 1
                
            start_char = current_offset
            normalized_text += page_text
            current_offset += len(page_text)
            end_char = current_offset
            
            page_offset_map.append({
                "page_number": page_number,
                "char_start": start_char,
                "char_end": end_char
            })
            
        return normalized_text, page_offset_map
        
    def get_page_for_offset(self, offset: int, offset_map: List[Dict[str, Any]]) -> int:
        for entry in offset_map:
            if entry["char_start"] <= offset <= entry["char_end"]:
                return entry["page_number"]
        if offset_map and offset >= offset_map[-1]["char_end"]:
            return offset_map[-1]["page_number"]
        return -1
