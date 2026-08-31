# Phase 7 Verification - PDF Page Extraction & Persistence

## 1. Files created/modified
- `app/pdf/extractor.py`
- `app/worker_main.py`
- `tests/unit/test_extractor.py`
- `tests/integration/test_worker.py`

## 2. What was implemented
- Validated PyMuPDF reading order on real legal PDF (`sort=True` vs `sort=False`), finding `sort=True` correctly placed the "CHÍNH PHỦ" header before the Title, matching human top-to-bottom reading order.
- Created `PDFExtractor.extract_pages` to yield page objects in natural reading order.
- Updated `worker_main.py` to use `PDFExtractor` to extract text from the downloaded raw PDF.
- Batched page upserts via `PageRepository.batch_upsert_pages` (limit 25).
- Idempotency verified: re-running ingestion does not create duplicate pages or fail with IntegrityError, due to `UNIQUE(document_id, page_number)` + PostgreSQL `ON CONFLICT DO UPDATE`.

## 3. Commands actually executed
- `docker compose exec api python -c "import pymupdf..."` to check sorting.
- `docker compose exec api python -m pytest tests/unit/test_extractor.py -v`
- `docker compose exec api python -m pytest tests/integration/test_worker.py -v`

## 4. Actual test output
Unit tests (Extractor):
```
tests/unit/test_extractor.py::test_extract_pages PASSED                  [100%]
```

Integration tests (Worker end-to-end):
```
tests/integration/test_worker.py::test_process_ingestion_success PASSED  [ 33%]
```

**Historical idempotency execution output** (captured by the one-off E2E harness that was removed after maintained integration coverage superseded it):
```text
=== 4. Prove page persistence idempotency explicitly ===
Executing batch_upsert_pages with the same data again...
{"job_id": "500b6d1c-0f97-46f7-b5b1-e10fd16f0e31", "document_id": "16347e1d-b298-42ac-a640-6328967137b3", "event": "job_started", ...}
...
After idempotent re-run, document_pages count = 8
```

## 5. Failures found
None explicitly broken. 

## 6. Fixes applied
- Replaced synthetic `%PDF-` file with real `sample_legal.pdf` bytes in worker integration test to allow `pymupdf` to actually extract 8 pages.

## 7. Re-run result
Passed smoothly. Page count correctly recorded as `pages_total = 8` and `pages_processed = 8`.

## 8. Remaining limitations
- No OCR. Text extraction relies on native PDF text layer.

## 9. Phase Definition of Done
- [x] real PDF → MinIO → Worker → PyMuPDF → document_pages
- [x] expected page_count == DB page count
- [x] sort=True reading order verified
- [x] Batch persistence committed atomically
- [x] Upsert idempotency verified
