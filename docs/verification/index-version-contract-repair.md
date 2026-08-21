# Block 2→3 Index-Version Contract Repair

Status: **PASS**

## Pre-flight

- Evaluation V1 SHA-256: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`
- Evaluation V2 SHA-256: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`
- Baseline backend: 212 collected, 212 passed, 0 failed, 8 warnings, 91.57 seconds.

## Confirmed defect

The automatic Block 2 completion hook in `app/processing_worker_main.py` created an indexing job with hardcoded `index_version="v1"`. The canonical manual endpoint and frozen Block 4 used `block3-v1`. This was a genuine frozen-contract integration defect, not reporting or intentionally supported legacy behavior.

## Minimal repair

- Added the single canonical owner `app/indexing/constants.py`:

  `CANONICAL_INDEX_VERSION = "block3-v1"`

- Updated the canonical manual endpoint, automatic Block 2 completion helper, Block 4 retrieval repository, and debug query to import that shared constant.
- No other production Python file contains the literal `block3-v1`.
- The worker still persists the version from its authoritative job record; active job-creation paths now always write the canonical value.
- No Block 2 processing, Block 3 worker/retry, queue, embedding, schema, or retrieval behavior was redesigned.

## Regression proof

Focused contract run: 10 passed, 0 failed.

Coverage:

- manual indexing endpoint creates `block3-v1` jobs;
- automatic Block 2 completion creates and enqueues `block3-v1` jobs;
- indexing worker persists `block3-v1` into all output rows;
- reindex/idempotency uses and retains `block3-v1`;
- Block 4 Dense/Lexical queries bind the shared canonical value;
- active canonical test flows contain no `v1` literal.

Final backend regression:

- Collected: 214
- Passed: 214
- Failed: 0
- Warnings: 8
- Duration: 91.71 seconds

Frontend:

- Test files: 5 passed
- Tests: 11 passed, 0 failed
- Duration: 947 ms
- Production build: PASS, 30 modules, 115 ms

## Legacy-row policy

Final development-database snapshot:

| Version | Chunk-index rows | Documents |
|---|---:|---:|
| `block3-v1` | 1,127 | 11 |
| `v1` | 1,999 | 130 |

Legacy `v1` jobs:

- COMPLETED: 128
- FAILED: 169
- PENDING: 98
- PROCESSING: 43

Among the 130 documents with legacy `v1` chunk indexes, zero currently have any `block3-v1` row and zero legacy chunk IDs have a matching canonical row. The development data are dominated by historical/test documents such as repeated `worker_test.pdf` records. Active Block 4 retrieval cannot read these rows because it binds `block3-v1`.

No legacy row was updated or deleted. The `v1` chunk-index count was 1,999 before the final full suite and remained 1,999 afterward, demonstrating that active test/canonical flows created no additional `v1` indexes.

Safe policy:

1. Historical `v1` rows may remain; active retrieval continues to ignore them.
2. Any retained document that must become searchable should be explicitly reindexed through the canonical endpoint.
3. Cleanup should be a separately approved, idempotent maintenance command with dry-run/reporting and document-retention review—not an automatic migration in this repair.

## Schema

- Public table count: 10, unchanged.
- New tables: 0.
- Migrations: none.
- Historical rows mutated: no.

