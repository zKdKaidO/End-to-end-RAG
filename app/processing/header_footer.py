import re
from typing import List, Dict

class HeaderFooterRemover:
    def __init__(self, check_lines: int = 3, frequency_threshold: float = 0.5):
        self.check_lines = check_lines
        self.frequency_threshold = frequency_threshold

    def _normalize(self, line: str) -> str:
        # Lowercase and remove all non-alphanumeric for matching purposes
        return re.sub(r'[\W_]+', '', line.lower())

    def remove_headers_footers(self, pages: List[str]) -> List[str]:
        if not pages:
            return pages

        num_pages = len(pages)
        if num_pages < 2:
            return self._remove_standalone_page_numbers(pages)

        # 1. Collect candidates
        first_lines_freq: Dict[str, int] = {}
        last_lines_freq: Dict[str, int] = {}
        
        page_lines = []
        for page in pages:
            lines = page.split('\n')
            page_lines.append(lines)
            
            # top lines
            for line in lines[:self.check_lines]:
                norm = self._normalize(line)
                if len(norm) > 5: # Ignore very short artifacts for frequency matching
                    first_lines_freq[norm] = first_lines_freq.get(norm, 0) + 1
                    
            # bottom lines
            for line in lines[-self.check_lines:]:
                norm = self._normalize(line)
                if len(norm) > 5:
                    last_lines_freq[norm] = last_lines_freq.get(norm, 0) + 1

        # 2. Identify frequent artifacts
        # To avoid false positives on 2-page documents (where 1/2 = 0.5), require > 1 absolute occurrence if num_pages <= 2,
        # or strictly > 0.5 frequency. We'll require both frequency >= threshold AND count > 1 to ensure it actually repeats.
        header_artifacts = set([k for k, v in first_lines_freq.items() if v / num_pages >= self.frequency_threshold and v > 1])
        footer_artifacts = set([k for k, v in last_lines_freq.items() if v / num_pages >= self.frequency_threshold and v > 1])

        # 3. Remove them
        cleaned_pages = []
        for lines in page_lines:
            # Remove top artifacts
            start_idx = 0
            for i, line in enumerate(lines[:self.check_lines]):
                norm = self._normalize(line)
                if norm in header_artifacts:
                    start_idx = i + 1
                else:
                    break
                    
            # Remove bottom artifacts
            end_idx = len(lines)
            for i, line in enumerate(reversed(lines[-self.check_lines:])):
                norm = self._normalize(line)
                if norm in footer_artifacts:
                    end_idx = len(lines) - (i + 1)
                else:
                    break
                    
            cleaned_lines = lines[start_idx:end_idx]
            
            # Also remove standalone page numbers at top/bottom
            cleaned_lines = self._strip_page_numbers(cleaned_lines)
            
            cleaned_pages.append("\n".join(cleaned_lines).strip())
            
        return cleaned_pages

    def _remove_standalone_page_numbers(self, pages: List[str]) -> List[str]:
        cleaned = []
        for page in pages:
            lines = page.split('\n')
            lines = self._strip_page_numbers(lines)
            cleaned.append("\n".join(lines).strip())
        return cleaned

    def _strip_page_numbers(self, lines: List[str]) -> List[str]:
        if not lines:
            return lines
            
        # Top page number
        if re.match(r'^(Trang\s*)?\d+\s*(/\s*\d+)?$', lines[0].strip(), re.IGNORECASE):
            lines = lines[1:]
            
        # Bottom page number
        if lines and re.match(r'^(Trang\s*)?\d+\s*(/\s*\d+)?$', lines[-1].strip(), re.IGNORECASE):
            lines = lines[:-1]
            
        return lines
