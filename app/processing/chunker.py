from typing import List, Dict, Any
import re
from app.processing.parser import LegalUnitData

class Chunker:
    def __init__(self, max_chars=1500, overlap=100):
        self.max_chars = max_chars
        self.overlap = overlap
        
    def generate_chunks(self, text: str, units: List[LegalUnitData], document_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        chunks = []
        chunk_index = 0
        
        # Helper to build parent context string
        def build_context(unit: LegalUnitData, ancestors: List[LegalUnitData]) -> str:
            # e.g., "Nghị định 135/2026/NĐ-CP, Chương I, Điều 1, Khoản 1"
            parts = []
            if document_metadata.get("document_number"):
                dt = document_metadata.get("document_type", "Văn bản")
                parts.append(f"{dt} {document_metadata.get('document_number')}")
                
            for anc in ancestors:
                if anc.unit_type == "PREAMBLE":
                    continue
                if anc.unit_number:
                    parts.append(f"{self._translate_type(anc.unit_type)} {anc.unit_number}")
                    
            if unit.unit_type != "PREAMBLE" and unit.unit_number:
                parts.append(f"{self._translate_type(unit.unit_type)} {unit.unit_number}")
                
            return " - ".join(parts)
            
        def process_unit(unit: LegalUnitData, ancestors: List[LegalUnitData]):
            nonlocal chunk_index
            
            # Determine the "own text" bounds.
            # Own text is from unit.start_char to the start of the first child, 
            # or unit.end_char if no children.
            own_end = unit.children[0].start_char if unit.children else unit.end_char
            own_text = text[unit.start_char:own_end].strip()
            
            if own_text:
                context_str = build_context(unit, ancestors)
                # Split if too long
                sub_chunks = self._split_text(own_text)
                
                for sc in sub_chunks:
                    # In embedding text, we prepend the context so the LLM knows where this is from
                    embedding_text = f"[{context_str}]\n{sc}" if context_str else sc
                    
                    chunks.append({
                        "chunk_index": chunk_index,
                        "legal_unit": unit,
                        "content_text": sc,
                        "embedding_text": embedding_text,
                        "char_start": unit.start_char + own_text.find(sc), # Approximate
                        "char_end": unit.start_char + own_text.find(sc) + len(sc)
                    })
                    chunk_index += 1
                    
            # Process children
            for child in unit.children:
                process_unit(child, ancestors + [unit])
                
        for u in units:
            process_unit(u, [])
            
        return chunks
        
    def _translate_type(self, unit_type: str) -> str:
        mapping = {
            "PART": "Phần",
            "CHAPTER": "Chương",
            "SECTION": "Mục",
            "ARTICLE": "Điều",
            "CLAUSE": "Khoản",
            "POINT": "Điểm"
        }
        return mapping.get(unit_type, unit_type)
        
    def _split_text(self, text: str) -> List[str]:
        # Split by sentence if longer than max_chars
        if len(text) <= self.max_chars:
            return [text]
            
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if not sentence: continue
            if len(current_chunk) + len(sentence) + 1 > self.max_chars and current_chunk:
                chunks.append(current_chunk.strip())
                # Start new chunk with overlap
                # Simple overlap: just take the last sentence of the previous chunk if it fits
                # But for simplicity, we'll just start fresh with the current sentence
                current_chunk = sentence
            else:
                current_chunk = current_chunk + " " + sentence if current_chunk else sentence
                
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        return chunks
