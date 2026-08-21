# Block 2 - Phase 1: Database + Job Queue + Worker

## 1. What was implemented
- Created 4 SQLAlchemy models reflecting the strictly frozen Block 2 database schema:
  - `DocumentProcessingJob`
  - `DocumentReconstruction`
  - `LegalUnit`
  - `Chunk`
- Updated `app/models/__init__.py` to import them for Alembic.
- Generated and ran an Alembic migration (`alembic revision --autogenerate` -> `alembic upgrade head`).
- Configured a new RQ queue `document-processing` in `app/queue/rq_client.py`.
- Wrote `app/processing_worker_main.py` which transitions the job from `PENDING` to `PROCESSING`.
- Integrated Block 2 trigger at the very end of Block 1's `process_ingestion` in `app/worker_main.py`.
- Added the `processing-worker` service to `docker-compose.yml` and launched it.

## 2. Commands Executed
```bash
docker compose run --rm migrate alembic revision --autogenerate -m "Add Block 2 models"
docker compose run --rm migrate alembic upgrade head
docker compose up -d processing-worker
docker compose exec api python -m pytest tests/integration/test_processing_queue.py -v -s
```

## 3. Actual Outputs
Alembic migration:
```text
INFO  [alembic.autogenerate.compare.tables] Detected added table 'document_processing_jobs'
INFO  [alembic.autogenerate.compare.tables] Detected added table 'document_reconstructions'
INFO  [alembic.autogenerate.compare.tables] Detected added table 'legal_units'
INFO  [alembic.autogenerate.compare.tables] Detected added table 'chunks'
```

Pytest (`test_processing_queue.py`):
```text
tests/integration/test_processing_queue.py::test_document_processing_queue 2026-08-18 02:35:41 [info     ] processing_job_enqueued        document_id=... processing_job_id=...
Status is PROCESSING
PASSED
```

## 4. Failures Encountered & Fixes Applied
- **Failure**: `migrate` container exited with code 1 due to `ImportError: cannot import name 'Base' from 'app.db.database'`.
- **Fix**: Adjusted imports across the new models from `app.db.database` to `app.db.base`.
- **Failure**: The worker test failed with `ImportError: cannot import name 'DatabaseError'`.
- **Fix**: Defined `DatabaseError` in `app/core/exceptions.py`.

## 5. Remaining Limitations
- The block 2 worker currently just transitions the state to `PROCESSING`. The actual processing pipeline (Cleaning, Header/Footer, Reconstruction) is not implemented yet.

## 6. Definition of Done Check
- [x] Schema matched frozen contract perfectly.
- [x] Worker added and consuming `document-processing` queue.
- [x] PENDING -> PROCESSING transition validated.
