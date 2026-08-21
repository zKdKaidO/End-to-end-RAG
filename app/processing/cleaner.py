import re
import unicodedata

class PageCleaner:
    def clean(self, text: str) -> str:
        if not text:
            return ""
            
        # 1. Unicode NFC normalization
        text = unicodedata.normalize("NFC", text)
        
        # 2. Line ending normalization
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        
        # 3. Trailing and safe whitespace cleanup
        lines = text.split("\n")
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line: # Remove completely empty lines? Let's keep them if we want to preserve paragraph breaks.
                # Actually, double newlines might mean paragraphs.
                # Let's just collapse 2+ spaces to 1 space.
                line = re.sub(r'[ \t]{2,}', ' ', line)
            cleaned_lines.append(line)
            
        # Collapse 3+ newlines into 2 newlines (paragraph break)
        text = "\n".join(cleaned_lines)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text
