# Block 2 - Phase 8: Metadata + Provenance
# Block 2 - Phase 9: Persistence + Idempotency
# Block 2 - Phase 10: Failure/Retry + Observability

## 1. What was implemented
- **Phase 8**: Iterated over generated chunks and enriched them with `metadata_json` (from Phase 5) and `provenance_json`. Added `page_start` and `page_end` by mapping character boundaries using the `page_offset_map`.
- **Phase 9**: Created `app/repositories/processing_repo.py` to persist `DocumentReconstruction`, `LegalUnit`, and `Chunk` records. Implemented idempotency using bulk `.delete()` prior to inserting new records for the same document (safely using SQLAlchemy cascades).
- **Phase 10**: Completed the `app/processing_worker_main.py` pipeline. Integrated all phases logically. Added structlog context (`bind_contextvars`) for request tracing. Leveraged RQ's native retry handling and job tracking, ensuring unhandled exceptions re-raise for explicit retry rather than swallowed failure.

## 2. Source Files Modified
- `app/processing_worker_main.py`
- `app/repositories/processing_repo.py`

## 3. Definition of Done Check
- [x] Context and mapping correctly appended to chunk structures.
- [x] Records securely persisted to PostgreSQL.
- [x] Worker pipeline completes end-to-end logically without errors.
- [x] Re-processing effectively wipes old records (Idempotency).
- [x] Retries configured.
