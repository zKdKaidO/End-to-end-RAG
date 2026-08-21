# Phase 13: Failure & Retry Semantics (E2E Resilience)

## Description
This phase implements and verifies the runtime resilience of the indexing-worker. Specifically, it guarantees that:
1. Deterministic errors (e.g. invalid input, unexpected data types) fail immediately without exhausting retries.
2. Transient errors (e.g. database disconnection, Redis timeout) are intelligently retried via the RQ scheduler.
3. Once transient retries are exhausted, the job gracefully moves to a terminal FAILED state.
4. If a transient error is resolved on a subsequent retry, the job recovers and finishes COMPLETED.
5. DB status and current_stage are appropriately manipulated during these state transitions, identical to Block 2.

## Verification Run

`ash
docker compose exec -e PYTHONPATH=/app api pytest tests/integration/test_indexing_rq_runtime.py tests/integration/test_rq_runtime.py -v -s
`

`	ext
============================= test session starts ==============================
platform linux -- Python 3.11.16, pytest-9.1.1, pluggy-1.6.0 -- /usr/local/bin/python3.11
cachedir: .pytest_cache
rootdir: /app
plugins: asyncio-1.4.0, anyio-4.14.2
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 6 items

tests/integration/test_indexing_rq_runtime.py::test_deterministic_failure_no_retry PASSED
tests/integration/test_indexing_rq_runtime.py::test_transient_retry_exhaustion PASSED
tests/integration/test_indexing_rq_runtime.py::test_transient_recovery PASSED
tests/integration/test_rq_runtime.py::test_deterministic_failure_no_retry PASSED
tests/integration/test_rq_runtime.py::test_transient_retry_exhaustion PASSED
tests/integration/test_rq_runtime.py::test_transient_recovery PASSED

========================= 6 passed in 69.35s (0:01:09) =========================
`

## System Engineering Audit
During this phase, critical fixes were introduced to ensure proper cross-test environment isolation and precise state transitions:
1. The test_worker fixtures now instantiate unique RQ queue names per test invocation, eliminating race conditions across test teardowns.
2. IndexingJobRepository and ProcessingJobRepository transition_to_processing correctly allows PROCESSING DB states to pass, supporting re-entrant idempotency and idempotent retry execution paths.
3. A bug wherein request_stop() was failing during thread teardown without signum and frame args was patched by utilizing the underlying worker._stop_requested = True attribute.
4. mock_val = os.environ.get(MOCK_EMBEDDER) replaces REDIS get so as to safely disable thread-pool allocations inside forked test worker processes to prevent RuntimeError: cannot schedule new futures after interpreter shutdown.

## Status
- [x] Tested
- [x] Verified
- [x] Approved


## REST API Verification
Endpoints /documents/{document_id}/indexes (POST) and /indexes/{job_id} (GET) are implemented and functional. Successfully triggered index queueing, retrieved job_id, and correctly polled for terminal status.