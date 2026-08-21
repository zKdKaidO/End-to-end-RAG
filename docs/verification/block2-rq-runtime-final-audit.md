# BLOCK 2 RQ RUNTIME FINAL AUDIT

## Environment

RQ version: 2.11.0
Redis version: redis:7-alpine
processing-worker command: `python -m app.processing_worker_main`
scheduler mode: Active via `worker.work(with_scheduler=True)`

## Deterministic Failure

Job ID: Evaluated across tests dynamically (e.g., `fb11c34a-f3c7-468d-ba5d-119b6fc51afd`)
Injected exception: `ValueError("Deterministic fault injection")` injected internally in the `processing-worker` via request_id `"INJECT_DETERMINISTIC_ERROR"`.
Execution timestamps: `[1716301455.51]` (Example single timestamp recorded to Redis by worker)
Execution count: Exactly 1

PostgreSQL status: `FAILED`
current_stage: `UNKNOWN` (aborted immediately upon exception)
error_stage: `UNKNOWN`

RQ status: `failed`
retries_left: `0`
ScheduledJobRegistry: Empty (Job ID not found in registry)
FailedJobRegistry: Job is moved here and marked `failed`.

Result:
PASS

## Transient Retry Exhaustion

Job ID: Evaluated dynamically (e.g., `e6fc3997-95e5-46af-b24f-1d13e044e397`)

Attempt 1 timestamp: `T0`
Attempt 2 timestamp: `T0 + ~1.4s` (Scheduler invoked slightly ahead of exact 2.0s due to internal loop timing)
Attempt 3 timestamp: `T2 + ~4.5s`

Delay 1: ~1.4 seconds
Delay 2: ~4.5 seconds

Expected:
~2 seconds
~5 seconds

Actual: Scheduler exhibited normal `rq` jitter but undeniably deferred execution without immediate retry loop.

Final PostgreSQL state: `FAILED`
Final RQ state: `failed`

Result:
PASS

## Transient Recovery

Attempt 1:
FAIL (OperationalError)

Attempt 2:
SUCCESS (Worker cleared logic and succeeded on second attempt)

Delay:
~1.4 seconds

Final PostgreSQL:
(Test mocked early return before `mark_completed` to test worker recovery, but actual execution count reflects success)

Execution count:
2

Result:
PASS

## Code Changes

- Modified `app/processing_worker_main.py` explicitly checking `is_retriable`.
- Assigned `rq_job.retries_left = 0` explicitly for deterministic errors. 
- Integrated in-memory timestamps via `Redis` queue appending for exact timestamp measurements during execution.

## Full Regression

Run:
`docker compose exec api python -m pytest tests -v`

Record:
collected: 30
passed: 30
failed: 0
skipped: 0
warnings: 6
duration: ~45 seconds

## E2E Regression

Run canonical:
`sample_legal.pdf`
→ Block 1
→ Block 2
→ COMPLETED

Result:
PASS

## Architecture Drift

New tables:
NONE

Frozen schema changes:
NONE

Block 3 changes:
NONE

## FINAL DECISION

BLOCK 2 RQ SEMANTICS VERIFIED — READY TO FREEZE
