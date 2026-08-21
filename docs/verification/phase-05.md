# Phase 5 Audit & Repair

## 1. Files created/modified
- `app/services/upload_service.py`
- `tests/integration/test_api.py`

## 2. What was implemented
- Validated real legal PDF upload behavior.
- Verified SHA-256 match.
- Verified deduplication logic, testing that no new records or jobs are created.
- Validated invalid inputs (oversized, invalid magic number).
- Simulated Object Storage failure (Minio offline) ensuring Document is marked FAILED and no job is enqueued.
- Simulated Queue failure (Redis offline) ensuring Job and Document are marked FAILED (Stage: QUEUE).
- Verified State regression protection (`transition_to_pending` fails if job is already PROCESSING).

## 3. Commands actually executed
- Copied `sample_legal.pdf` to `tests/fixtures/sample_legal.pdf`.
- `docker compose exec api python -c "..."` to extract SHA-256 of real PDF.
- `docker compose exec api python -m pytest tests/integration/test_minio_client.py -v` (duration: 12.37s).
- `docker compose exec api python -m pytest tests/integration/test_api.py -v` (duration: 1.22s).

## 4. Actual test output
All 5 MinIO integration tests PASSED. (12.37s).
All 7 Upload API integration tests PASSED. (1.22s).

## 5. Failures found
None explicitly broken since previous phase, but test coverage was improved to match all audit criteria.

## 6. Fixes applied
- Handled clean dependency installation by appending `python-multipart` to `requirements.txt`.
- Executed `docker compose build --no-cache api worker migrate` to verify.

## 7. Re-run result
Test suite passes cleanly.

## 8. Remaining limitations
- Queue failures leave orphaned uploaded files in MinIO (no rollback logic exists yet). Documented policy: leave artifacts for debugging.

## 9. Phase Definition of Done
- [x] real legal PDF accepted
- [x] HTTP response correct
- [x] SHA-256 verified
- [x] PostgreSQL document created
- [x] ingestion job created
- [x] PDF exists in MinIO
- [x] downloaded PDF matches source
- [x] actual RQ job exists
- [x] duplicate behavior verified
- [x] invalid file tests PASS
- [x] max size test PASS
- [x] MinIO failure path PASS
- [x] Redis failure path PASS
- [x] state regression test PASS
- [x] MinIO suite PASS
- [x] clean Docker rebuild PASS
