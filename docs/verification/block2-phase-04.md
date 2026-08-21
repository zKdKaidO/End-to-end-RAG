# Block 2 - Phase 4: Document Reconstruction + Page Offset Map

## 1. What was implemented
- Created `app/processing/reconstruction.py` containing `DocumentReconstructor`.
- Implemented `reconstruct(pages)` to merge cleaned pages into a continuous string (`normalized_text`), inserting newlines between pages.
- Generated a `page_offset_map` tracking `char_start` and `char_end` for each page.
- Implemented `get_page_for_offset()` to map any character offset in the continuous text back to its source page using the offset map, handling gap characters (newlines inserted between pages) safely by attributing them to the preceding page boundary.
- Wrote tests in `tests/unit/test_reconstruction.py`.

## 2. Commands Executed
```bash
docker compose exec api python -m pytest tests/unit/test_reconstruction.py -v
```

## 3. Actual Outputs
```text
tests/unit/test_reconstruction.py::test_document_reconstruction PASSED
tests/unit/test_reconstruction.py::test_offset_gap_handling PASSED
```

## 4. Failures Encountered & Fixes Applied
- **Failure**: Newlines inserted between pages were creating 1-character gaps not covered strictly by `< entry["char_end"]`.
- **Fix**: Modified the condition to `<= entry["char_end"]` so that the gap character is robustly mapped to the originating boundary.

## 5. Remaining Limitations
- A binary search could be slightly faster than linear search for massive documents (1000+ pages), but linear search is fast enough for typical legal documents (e.g. 50-200 pages).

## 6. Definition of Done Check
- [x] Ordered, monotonic, non-overlapping `page_offset_map`.
- [x] Traceable offset -> source page.
- [x] Cross-page boundary mapping tested.
