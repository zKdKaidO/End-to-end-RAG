# Block 2 - Phase 2: Page Cleaning

## 1. What was implemented
- Created `app/processing/cleaner.py` containing `PageCleaner` class.
- Implemented deterministic cleaning operations:
  - Unicode NFC normalization using `unicodedata.normalize`.
  - Line ending normalization (`\r\n` and `\r` to `\n`).
  - Leading, trailing and safe whitespace cleanup (collapsing multiple spaces `[ \t]{2,}` into a single space, removing leading/trailing spaces).
  - Collapsing 3+ consecutive newlines into 2 newlines to preserve paragraph boundaries but remove extreme vertical gaps.
- The cleaning preserves legal text (e.g. `Điều 1.`, `1.`, `a)` etc.) as it only collapses whitespaces and does not rewrite text.
- Created `tests/unit/test_cleaner.py` to verify behavior.

## 2. Commands Executed
```bash
docker compose exec api python -m pytest tests/unit/test_cleaner.py -v
```

## 3. Actual Outputs
```text
tests/unit/test_cleaner.py::test_page_cleaner PASSED                     [100%]
```

## 4. Failures Encountered & Fixes Applied
- None. The deterministic regex logic worked first try.

## 5. Remaining Limitations
- Strip removes indentation. While visual indentation is lost, semantic parsing of legal documents typically relies on regex markers (`Điều`, `Khoản`, `1.`, `a)`) rather than whitespace indentation, so this is deemed safe and correct.

## 6. Definition of Done Check
- [x] Noise normalized.
- [x] Legal content preserved.
- [x] Numbering preserved.
- [x] Vietnamese Unicode preserved.
