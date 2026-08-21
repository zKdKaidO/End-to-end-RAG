# Block 2 - Phase 6: Legal Structure Parser

## 1. What was implemented
- Created `app/processing/parser.py` containing `LegalParser`.
- Implemented a deterministic state machine based on level hierarchy:
  - `0`: PREAMBLE
  - `1`: PART (Phần)
  - `2`: CHAPTER (Chương)
  - `3`: SECTION (Mục)
  - `4`: ARTICLE (Điều)
  - `5`: CLAUSE (Khoản - 1., 2., 3.)
  - `6`: POINT (Điểm - a), b), c))
- The parser keeps track of the parent stack, popping back to the correct level when a new unit of equal or higher hierarchy is encountered.
- Handles title lookahead for units where the title is placed on the subsequent line (e.g. `Chương I\nQUY ĐỊNH CHUNG`).
- Populates a tree of `LegalUnitData` with `char_start` and `char_end` for accurate mapping.
- Wrote unit test `tests/unit/test_parser.py` representing a multi-level legal document (Chapter -> Article -> Clause -> Point).

## 2. Commands Executed
```bash
docker compose exec api python -m pytest tests/unit/test_parser.py -v
```

## 3. Actual Outputs
```text
tests/unit/test_parser.py::test_legal_parser PASSED
```

## 4. Failures Encountered & Fixes Applied
- **Failure**: In the unit test, `chuong1.title` was empty because `QUY ĐỊNH CHUNG` was on the line following `Chương I`.
- **Fix**: Added `get_title()` lookahead logic to gracefully fetch the next non-empty line as the title if it doesn't match another legal unit boundary.

## 5. Remaining Limitations
- Only supports standard Vietnamese legal numbering. Documents deviating wildly from this structure will just lump text into their nearest recognized parent.

## 6. Definition of Done Check
- [x] State machine parses correctly.
- [x] `PREAMBLE` implicitly captured.
- [x] `char_start` and `char_end` accurately bounded.
- [x] Evaluated against fixture structure.
