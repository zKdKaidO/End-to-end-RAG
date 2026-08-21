import re
from typing import List, Dict, Any, Optional

class LegalUnitData:
    def __init__(self, unit_type: str, unit_number: str, title: str, start_char: int, level: int):
        self.unit_type = unit_type
        self.unit_number = unit_number
        self.title = title
        self.start_char = start_char
        self.end_char = -1
        self.level = level
        self.children: List['LegalUnitData'] = []
        
    def to_dict(self):
        return {
            "unit_type": self.unit_type,
            "unit_number": self.unit_number,
            "title": self.title,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "level": self.level,
            "children": [c.to_dict() for c in self.children]
        }

class LegalParser:
    def __init__(self):
        # Level hierarchy
        self.HIERARCHY = {
            "PREAMBLE": 0,
            "PART": 1,     # Phần
            "CHAPTER": 2,  # Chương
            "SECTION": 3,  # Mục
            "ARTICLE": 4,  # Điều
            "CLAUSE": 5,   # Khoản (1., 2., 3.)
            "POINT": 6     # Điểm (a), b), c))
        }
        
    def parse(self, text: str) -> List[LegalUnitData]:
        units = []
        
        # We process line by line, but keep track of char offset
        # A regex pattern to detect headers.
        
        # Part: Phần I, Phần thứ nhất
        # Chapter: Chương I, Chương II
        # Section: Mục 1, Mục 2
        # Article: Điều 1., Điều 2.
        # Clause: 1., 2., 3. (At the start of a paragraph)
        # Point: a), b), c) (At the start of a paragraph)
        
        lines = text.split('\n')
        
        root = LegalUnitData("ROOT", "", "", 0, -1)
        stack = [root]
        
        current_offset = 0
        
        # Preamble implicit start
        preamble = LegalUnitData("PREAMBLE", "", "Preamble", 0, self.HIERARCHY["PREAMBLE"])
        root.children.append(preamble)
        stack.append(preamble)
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            line_len = len(line) + 1 # +1 for \n
            
            if not line_stripped:
                current_offset += line_len
                continue
                
            matched = False
            
            # Helper to get next line for title if current is empty
            def get_title(current_title: str) -> str:
                if current_title:
                    if current_title.startswith('.') or current_title.startswith(':'):
                        return current_title[1:].strip()
                    return current_title
                # Look ahead for title
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    if next_line:
                        # If next line looks like a new unit, don't consume it
                        if re.match(r'^(Phần|Chương|Mục|Điều|1\.|a\))', next_line, re.IGNORECASE):
                            return ""
                        return next_line
                return ""
            
            # 1. PART
            part_match = re.match(r'^Phần\s+([A-Z0-9IVX]+|thứ\s+\w+)(.*)', line_stripped, re.IGNORECASE)
            if part_match:
                number = part_match.group(1).strip()
                title = get_title(part_match.group(2).strip())
                self._add_unit(stack, "PART", number, title, current_offset)
                matched = True
                
            # 2. CHAPTER
            elif re.match(r'^Chương\s+([A-Z0-9IVX]+)(.*)', line_stripped, re.IGNORECASE):
                chap_match = re.match(r'^Chương\s+([A-Z0-9IVX]+)(.*)', line_stripped, re.IGNORECASE)
                number = chap_match.group(1).strip()
                title = get_title(chap_match.group(2).strip())
                self._add_unit(stack, "CHAPTER", number, title, current_offset)
                matched = True
                
            # 3. SECTION
            elif re.match(r'^Mục\s+([0-9]+)(.*)', line_stripped, re.IGNORECASE):
                sec_match = re.match(r'^Mục\s+([0-9]+)(.*)', line_stripped, re.IGNORECASE)
                number = sec_match.group(1).strip()
                title = get_title(sec_match.group(2).strip())
                self._add_unit(stack, "SECTION", number, title, current_offset)
                matched = True
                
            # 4. ARTICLE
            elif re.match(r'^Điều\s+([0-9]+)\.(.*)', line_stripped, re.IGNORECASE):
                art_match = re.match(r'^Điều\s+([0-9]+)\.(.*)', line_stripped, re.IGNORECASE)
                number = art_match.group(1).strip()
                title = get_title(art_match.group(2).strip())
                self._add_unit(stack, "ARTICLE", number, title, current_offset)
                matched = True
                
            # 5. CLAUSE
            elif re.match(r'^([0-9]+)\.\s(.*)', line_stripped):
                clause_match = re.match(r'^([0-9]+)\.\s(.*)', line_stripped)
                number = clause_match.group(1).strip()
                self._add_unit(stack, "CLAUSE", number, "", current_offset)
                matched = True
                
            # 6. POINT
            elif re.match(r'^([a-zđ])\)\s(.*)', line_stripped):
                point_match = re.match(r'^([a-zđ])\)\s(.*)', line_stripped)
                number = point_match.group(1).strip()
                self._add_unit(stack, "POINT", number, "", current_offset)
                matched = True
                
            current_offset += line_len
            
        # Close all open units
        while len(stack) > 1:
            unit = stack.pop()
            unit.end_char = len(text)
            
        return root.children
        
    def _add_unit(self, stack, unit_type, number, title, start_char):
        level = self.HIERARCHY[unit_type]
        
        # Pop stack until we find a parent with a strictly lower level number (higher hierarchy)
        # E.g. If current is ARTICLE (4), we pop until we find SECTION (3) or CHAPTER (2) or PART (1) or ROOT (-1)
        # PREAMBLE is 0, so it will pop PREAMBLE if adding PART/CHAPTER.
        while stack and stack[-1].level >= level:
            closed_unit = stack.pop()
            # If we don't know exact end char (without lookahead), 
            # the start_char of the new unit is the end_char of the closed unit
            closed_unit.end_char = start_char - 1
            
        parent = stack[-1]
        
        # Close the PREAMBLE properly if we are inserting something else at top level
        # Wait, if parent is PREAMBLE, but its level is 0, then a PART(1) will NOT pop PREAMBLE.
        # But PREAMBLE should be closed when the first PART or CHAPTER begins!
        # Ah, PREAMBLE is a peer to PART/CHAPTER, not a parent!
        # So PREAMBLE should have level = 1 (or 2 if CHAPTER is top).
        # Actually PREAMBLE is just the top text. Let's force PREAMBLE to close when first Article/Chapter/Part starts.
        if stack[-1].unit_type == "PREAMBLE":
            preamble = stack.pop()
            preamble.end_char = start_char - 1
            parent = stack[-1] # which should be ROOT
            
        new_unit = LegalUnitData(unit_type, number, title, start_char, level)
        parent.children.append(new_unit)
        stack.append(new_unit)
