# Phase 6 Verification - Redis / RQ Worker

## 1. Files created/modified
- `app/worker_main.py`
- `app/queue/rq_client.py`
- `tests/integration/test_worker.py`

## 2. What was implemented
- Defined `process_ingestion` job entrypoint.
- Integrated `rq` explicit `Retry` logic: `Retry(max=2, interval=[2, 5])`.
- Corrected RQ Worker initialization without legacy `Connection` context block.
- Bounded retries:
  - Added transient failure catch block checking `rq_job.retries_left > 0`.
  - Application terminal failure sets `FAILED` state if `retries_left == 0` or `None`.
- Never swallowed exceptions: explicitly `raise` at boundary to ensure RQ's built-in retry and dead-letter queue mechanism function correctly.

## 3. Commands actually executed
- `docker compose exec api python -m pytest tests/integration/test_worker.py -v`

## 4. Actual test output
```
tests/integration/test_worker.py::test_process_ingestion_success PASSED  [ 33%]
tests/integration/test_worker.py::test_process_ingestion_terminal_failure PASSED [ 66%]
tests/integration/test_worker.py::test_process_ingestion_transient_failure PASSED [100%]
```

## 5. Failures found
- `DetachedInstanceError` occurred when closing DB session before mapping out IDs inside the test cases.
- Unique constraint violations when re-running tests without randomized hashes.

## 6. Fixes applied
- `doc_id` and `job_id` extracted from ORM objects before session commit/close.
- Hashed hashes using `uuid4` prefix for isolation in tests.

## 7. Re-run result
- All 3 failure & success scenario boundary tests PASSED.

## 8. Remaining limitations
- The extraction step is a stub. Needs to be replaced in Phase 7.

## 9. Phase Definition of Done
- [x] receive job_id
- [x] load ingestion_job + document
- [x] transition to PROCESSING
- [x] set current_stage = DOWNLOAD
- [x] explicit RQ retry policy
- [x] transient failure preserves state
- [x] terminal failure sets FAILED
- [x] exception boundary does not swallow exception
- [x] integration test for all 3 paths PASS
