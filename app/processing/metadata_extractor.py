import re
from typing import Dict, Any

class MetadataExtractor:
    def extract(self, text: str) -> Dict[str, Any]:
        metadata = {
            "document_type": None,
            "document_number": None,
            "issuing_authority": None,
            "issued_date": None,
            "title": None
        }
        
        # Look at the first 2000 chars roughly
        header_text = text[:2000]
        
        # 1. Issuing authority (usually at the very top, before CỘNG HÒA)
        # Or just CHÍNH PHỦ
        if "CHÍNH PHỦ" in header_text.upper():
            metadata["issuing_authority"] = "Chính phủ"
        elif "QUỐC HỘI" in header_text.upper():
            metadata["issuing_authority"] = "Quốc hội"
            
        # 2. Document number
        number_match = re.search(r'Số:\s*([^\s\n]+)', header_text, re.IGNORECASE)
        if number_match:
            metadata["document_number"] = number_match.group(1).strip()
            
        # 3. Document type
        if re.search(r'\bNGHỊ ĐỊNH\b', header_text, re.IGNORECASE):
            metadata["document_type"] = "Nghị định"
        elif re.search(r'\bLUẬT\b', header_text, re.IGNORECASE):
            metadata["document_type"] = "Luật"
        elif re.search(r'\bQUYẾT ĐỊNH\b', header_text, re.IGNORECASE):
            metadata["document_type"] = "Quyết định"
            
        # 4. Issued date
        date_match = re.search(r'ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})', header_text, re.IGNORECASE)
        if date_match:
            day, month, year = date_match.groups()
            metadata["issued_date"] = f"{year}-{int(month):02d}-{int(day):02d}"
            
        # 5. Title
        # Title is usually below Document type and spans until Căn cứ...
        # Look for NGHỊ ĐỊNH\n(.*?)\n\nCăn cứ
        type_str = metadata["document_type"].upper() if metadata["document_type"] else "NGHỊ ĐỊNH"
        title_match = re.search(fr'{type_str}\s*\n(.*?)\s*Căn cứ', header_text, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = title_match.group(1)
            # Remove excessive newlines/spaces
            title = re.sub(r'\s+', ' ', title).strip()
            metadata["title"] = title
            
        return metadata
