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
            "APPENDIX": 2, # Phụ lục
            "CHAPTER": 2,  # Chương
            "SECTION": 3,  # Mục
            "TABLE_CATEGORY": 4,
            "ARTICLE": 4,  # Điều
            "CLAUSE": 5,   # Khoản (1., 2., 3.)
            "POINT": 6     # Điểm (a), b), c))
        }
        
    def parse(self, text: str) -> List[LegalUnitData]:
        units = []
        # Appendix tables use a leading integer as the category identifier.
        # Treating every numeric line as a category is unsafe: extracted cells
        # also begin with values such as "1 tiết" and "6 giờ".  A category
        # therefore has to advance the top-level table sequence for its own
        # appendix (1, 2, 3, ...); the first category additionally rejects
        # obvious conversion/value rows.  This keeps adjacent real categories
        # separate without turning table-cell values into hierarchy roots.
        appendix_next_category: dict[int, int] = {}
        
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

            # A heading-looking prefix is only a *candidate*.  PDF extraction
            # commonly yields prose such as "Chương trình ..." and page
            # timestamps at line boundaries; neither establishes a legal
            # hierarchy node.  The candidate recognizers below require a
            # complete, structurally plausible identifier before `_add_unit`
            # is reached.

            # Helper to get next line for title if current is empty
            def get_title(current_title: str) -> str:
                if current_title:
                    cleaned = current_title.lstrip(".:-— ").strip()
                    return cleaned if self._valid_heading_title(cleaned) else ""
                # Look ahead for title
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    if next_line:
                        # If next line looks like a new unit, don't consume it
                        if self._candidate_kind(next_line) is not None:
                            return ""
                        return next_line if self._valid_heading_title(next_line) else ""
                return ""

            # Some text-native PDFs concatenate a footer or a preceding point
            # with the next article heading.  An embedded Article is accepted
            # only when it advances the current article numbering and has a
            # heading-like continuation; ordinary citations such as "theo
            # Điều 12." remain ordinary text.
            embedded_article = self._embedded_article_candidate(line_stripped, stack)
            if embedded_article is not None:
                article_number, article_title, offset_in_line = embedded_article
                self._add_unit(
                    stack, "ARTICLE", article_number, get_title(article_title),
                    current_offset + offset_in_line,
                )
                matched = True
            
            # 1. PART
            part_match = None if matched else re.match(
                r'^(?i:Phần)\s+((?:[IVXLCDM]+)|(?:\d+)|(?:thứ\s+[\wÀ-ỹ-]+))(?=\s|[.:-—]|$)(.*)$',
                line_stripped,
            )
            if part_match:
                number = part_match.group(1).strip()
                title = get_title(part_match.group(2).strip())
                self._add_unit(stack, "PART", number, title, current_offset)
                matched = True

            elif not matched and (appendix_match := re.match(
                r'^(?i:Phụ\s+lục)\s+([0-9IVXLCDM]+)(?=\s|[.:-—]|$)(.*)$', line_stripped
            )):
                number = appendix_match.group(1).strip()
                title = get_title(appendix_match.group(2).strip())
                self._add_unit(stack, "APPENDIX", number, title, current_offset)
                matched = True
                
            # 2. CHAPTER
            elif not matched and (chap_match := re.match(
                r'^(?i:Chương)\s+([IVXLCDM]+)(?=\s|[.:-—]|$)(.*)$', line_stripped
            )):
                number = chap_match.group(1).strip()
                title = get_title(chap_match.group(2).strip())
                self._add_unit(stack, "CHAPTER", number, title, current_offset)
                matched = True
                
            # 3. SECTION
            elif not matched and (sec_match := re.match(
                r'^(?i:Mục)\s+([0-9]+)(?=\s|[.:-—]|$)(.*)$', line_stripped
            )):
                number = sec_match.group(1).strip()
                title = get_title(sec_match.group(2).strip())
                self._add_unit(stack, "SECTION", number, title, current_offset)
                matched = True
                
            # 4. ARTICLE
            elif not matched and (art_match := re.match(r'^(?i:Điều)\s+([0-9]+)\s*\.(.*)$', line_stripped)):
                number = art_match.group(1).strip()
                title = get_title(art_match.group(2).strip())
                self._add_unit(stack, "ARTICLE", number, title, current_offset)
                matched = True
                
            # 5. CLAUSE
            elif not matched and (clause_match := re.match(r'^([0-9]+)\.\s+(.*)$', line_stripped)):
                number = clause_match.group(1).strip()
                if any(unit.unit_type == "ARTICLE" for unit in stack):
                    self._add_unit(stack, "CLAUSE", number, "", current_offset)
                    matched = True
                
            # 6. POINT
            elif not matched and (point_match := re.match(r'^([a-zđ])\)\s+(.*)$', line_stripped)):
                number = point_match.group(1).strip()
                if any(unit.unit_type == "CLAUSE" for unit in stack):
                    self._add_unit(stack, "POINT", number, "", current_offset)
                    matched = True

            elif not matched and re.match(r'^\d+$', line_stripped) and self._is_table_category(
                stack,
                line_stripped,
                get_title(""),
                appendix_next_category,
            ):
                title = get_title("")
                previous = lines[i - 1].strip() if i else ""
                if previous.endswith((",", ":", "—", "-")) and title:
                    title = f"{previous} {title}"
                if self._valid_heading_title(title):
                    self._add_unit(stack, "TABLE_CATEGORY", line_stripped, title, current_offset)
                    appendix = self._active_appendix(stack)
                    if appendix is not None:
                        appendix_next_category[id(appendix)] = int(line_stripped) + 1
                    matched = True

            elif not matched and (table_match := re.match(r'^(\d+)\s+(.+)$', line_stripped)) and self._is_table_category(
                stack,
                table_match.group(1),
                table_match.group(2).strip(),
                appendix_next_category,
            ):
                title = table_match.group(2).strip()
                if self._valid_heading_title(title):
                    self._add_unit(stack, "TABLE_CATEGORY", table_match.group(1), title, current_offset)
                    appendix = self._active_appendix(stack)
                    if appendix is not None:
                        appendix_next_category[id(appendix)] = int(table_match.group(1)) + 1
                    matched = True
                
            current_offset += line_len
            
        # Close all open units
        while len(stack) > 1:
            unit = stack.pop()
            unit.end_char = len(text)
            
        return root.children

    @staticmethod
    def _valid_heading_title(value: str) -> bool:
        """Reject extraction noise before it becomes legal structure.

        A title can be empty for a clause or point but a top-level heading
        must have human text and may not be a timestamp/page-fragment.
        """
        if not value or len(value) > 400:
            return False
        if re.search(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", value):
            return False
        return any(character.isalpha() for character in value)

    @staticmethod
    def _active_appendix(stack: list[LegalUnitData]) -> LegalUnitData | None:
        return next(
            (unit for unit in reversed(stack) if unit.unit_type == "APPENDIX"),
            None,
        )

    @classmethod
    def _is_table_category(
        cls,
        stack: list[LegalUnitData],
        number: str,
        title: str,
        expected_by_appendix: dict[int, int],
    ) -> bool:
        appendix = cls._active_appendix(stack)
        if appendix is None or not number.isdigit():
            return False

        expected = expected_by_appendix.get(id(appendix), 1)
        if int(number) != expected or not cls._valid_heading_title(title):
            return False

        # Before the first actual category, tabular conversion rules can look
        # like "1 tiết học = ...".  They are values, not semantic roots.
        if expected == 1:
            normalized = title.casefold()
            if (
                "=" in title
                or "tiết học" in normalized
                or "giờ tín chỉ" in normalized
                or "phút" in normalized
            ):
                return False

        return True

    @staticmethod
    def _candidate_kind(line: str) -> str | None:
        if re.match(r'^(?i:Phần)\s+(?:(?:[IVXLCDM]+)|(?:\d+)|(?:thứ\s+[\wÀ-ỹ-]+))(?=\s|[.:-—]|$)', line):
            return "PART"
        if re.match(r'^(?i:Phụ\s+lục)\s+[0-9IVXLCDM]+(?=\s|[.:-—]|$)', line):
            return "APPENDIX"
        if re.match(r'^(?i:Chương)\s+[IVXLCDM]+(?=\s|[.:-—]|$)', line):
            return "CHAPTER"
        if re.match(r'^(?i:Mục)\s+\d+(?=\s|[.:-—]|$)', line):
            return "SECTION"
        if re.match(r'^(?i:Điều)\s+\d+\s*\.', line):
            return "ARTICLE"
        if re.match(r'^\d+\.\s+', line):
            return "CLAUSE"
        if re.match(r'^[a-zđ]\)\s+', line):
            return "POINT"
        return None

    @staticmethod
    def _embedded_article_candidate(
        line: str, stack: list[LegalUnitData],
    ) -> tuple[str, str, int] | None:
        match = re.search(r'(?<![\wÀ-ỹ])(?i:Điều)\s+([0-9]+)\s*\.\s*(.+)$', line)
        if match is None or match.start() == 0:
            return None
        prior_articles = [
            int(unit.unit_number) for unit in stack
            if unit.unit_type == "ARTICLE" and unit.unit_number.isdigit()
        ]
        if not prior_articles or int(match.group(1)) != prior_articles[-1] + 1:
            return None
        title = match.group(2).strip()
        if not LegalParser._valid_heading_title(title):
            return None
        return match.group(1), title, match.start()
        
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
