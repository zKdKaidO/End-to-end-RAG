# Phase 6 — Indexing Worker Execution Logic

## Files Inspected
- `app/indexing_worker_main.py`
- `tests/integration/test_indexing_worker.py`

## Files Created/Modified
- `app/indexing_worker_main.py`
- `tests/integration/test_indexing_worker.py`

## What was implemented
- Created `indexing_worker_main.py` to listen on the `document-indexing` queue.
- Orchestrated embedding flow: `LOAD_CHUNKS` -> `EMBEDDING` -> `PERSIST_INDEX` -> `FINALIZE`.
- Persisted job stages securely in the `IndexingJob` table.
- Exception handling intercepts exceptions, records the exact `error_stage`, `error_type`, and `error_message`, and fails the job immediately unless it is transient (e.g., Redis/DB timeout).
- Implemented `test_indexing_worker_success` mocking the embedder to run fast.
- Implemented `test_indexing_worker_failure` to prove failures set state accurately.

## Commands executed
- Developed unit tests.

## Actual outputs
- Worker safely and fully completes workflows or fails gracefully.

## Definition of Done
- `indexing_worker_main.py` implemented.
- State machine enforced.
- Tested failure scenarios.
