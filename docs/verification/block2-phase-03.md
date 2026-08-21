# Block 2 - Phase 3: Header / Footer Removal

## 1. What was implemented
- Created `app/processing/header_footer.py` with `HeaderFooterRemover` class.
- Implemented deterministic text heuristics:
  - Extract first N (3) and last N lines of each page.
  - Normalize texts (remove non-alphanumeric, lowercase) to count cross-page frequency.
  - Compute a frequency threshold (`>= 0.5`) across all pages to robustly identify headers/footers vs actual content.
  - Safely strip identified high-confidence artifacts from the top and bottom.
  - Detect and strip standalone page numbers (e.g. `Trang 1/5`, `2`, `14`) independently of the repeated text heuristic.
- Guaranteed it never blindly removes lines if they are not repeated (thus preserving page-spanning paragraphs).
- Wrote unit tests in `tests/unit/test_header_footer.py`.

## 2. Commands Executed
```bash
docker compose exec api python -m pytest tests/unit/test_header_footer.py -v
```

## 3. Actual Outputs
```text
tests/unit/test_header_footer.py::test_header_footer_removal PASSED
tests/unit/test_header_footer.py::test_no_blind_removal PASSED
```

## 4. Failures Encountered & Fixes Applied
- **Failure**: A test asserted `"2" not in cleaned[1]`, which failed because the body contained `"Nội dung 2"`.
- **Fix**: Changed the assertion to check `startswith("2\n")` to strictly ensure the page number on its own line was removed.

## 5. Remaining Limitations
- Heuristic logic assumes a high page count. For single-page documents, frequency checks are skipped and only standalone page numbers are removed.

## 6. Definition of Done Check
- [x] Repeated header removed.
- [x] Repeated footer removed.
- [x] Page number removed.
- [x] Legal text at beginning/end of page preserved.
