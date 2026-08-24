# Final End-to-End Product V1 Gate — Repaired Candidate

Audit window: 2026-08-24 08:18:14Z–08:24:12Z  
Run: `20260824T081814Z-ba667e`  
Decision: **READY**

The replacement API/worker candidate passed every complete-gate scenario and repaired both release-blocking processing/deletion races. The active race jobs exited normally with structured lifecycle diagnostics, no database exception, no new failed-registry entry, no late derived data, and no resurrection.

The complete per-scenario runtime snapshot is preserved at `evaluation/e2e/final_product_v1_gate_runtime.json` (SHA-256 `f5349958258948d879ad4790a9122245e28f1e6eb3f3f4897d3f5fa9c99450f5`).

The rejected candidate remains preserved at:

- `evaluation/e2e/final_product_v1_gate_previous_failed.json` (SHA-256 `6b67b2601fb62abb54abc2878b510f96f8758c5e0a24bf9448ee8d9783613f54`)
- `docs/verification/final-end-to-end-product-v1-gate-previous-failed.md` (SHA-256 `14c7436d5a1b5f27c3b4e1736eda4a26aab2fb5f6c1969ad054a07668e826a14`)

## Release Candidate Identity

- API/workers: `sha256:0b7bd04429e2cdbb6459866832fbcfd836591ba4c2c384f99a7658b5b05783a0`
- Frontend: `sha256:0609b046064912f679fd589cc6563c97b01ce21a0f6c5673eea70273e7e6dc74`
- Model: `qwen3.5:9b`
- Model digest: `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`
- Prompt: `legal-rag-v2`
- Prompt SHA-256: `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee`
- Alembic: `auth_authorization_v1`
- pgvector: `0.5.1`
- Backup ID: `20260823T161115Z-54300867`

Container inspection confirmed that the isolated API, ingestion worker, processing worker, and indexing worker all ran the new digest. The unchanged frontend ran its prior verified digest. PostgreSQL, MinIO, Redis, model-cache, recovery-control, and backup volumes were preserved.

## Root Cause and Narrow Repair

The rejected worker performed long CPU processing while retaining assumptions about an ORM job/document that lifecycle cleanup could delete. It later attempted either a stage update against a cascade-deleted processing-job row (`StaleDataError`) or a reconstruction insert against a deleted canonical document (`ForeignKeyViolation`/`IntegrityError`).

The repair changes only Block 2 lifecycle persistence/finalization:

1. Expensive cleaning, reconstruction, legal parsing, and chunk generation still run without a lifecycle lock.
2. Immediately before durable persistence, a short transaction re-fetches and locks the canonical `Document` row using `SELECT ... FOR UPDATE`, matching canonical GC's lock boundary.
3. If deletion already won, the worker rolls back and exits normally with `PROCESSING_ABORTED_TARGET_DELETED`.
4. If persistence won, reconstruction, legal units, chunks, processing counts, `COMPLETED`, `DONE`, and `finished_at` commit atomically. Deletion then proceeds and cascades those rows.
5. Stage transitions use conditional SQL updates and inspect rowcount. A missing job with a missing document is expected lifecycle termination; a missing job while the canonical document remains is a real error.
6. Index handoff rechecks the canonical document and does not enqueue a late Block 3 job for a deleted or unreferenced target.

No `StaleDataError` or `IntegrityError` catch-and-ignore path was introduced. Database exceptions remain genuine failures.

## Deterministic Race Verification

The real-PostgreSQL tests in `tests/integration/test_processing_deletion_race.py` use barriers/events at exact lifecycle points; no timing sleep determines race ordering.

| Interleaving | Result | Key assertion |
|---|---:|---|
| Document delete wins | PASS | Clean worker exit; no canonical/derived rows; no failed job |
| Account delete + unique canonical | PASS | User and canonical target remain deleted; no late write |
| Account delete + shared canonical | PASS | Alice removed; Bob grant/canonical retained; processing completes |
| Worker persistence wins | PASS | GC waits on the lifecycle lock, then deletes all derived rows after commit |

Result: 4 passed, 0 failed, 6 warnings, 1.22 seconds. StaleDataError `0`; ForeignKeyViolation `0`; unexpected lifecycle exceptions `0`; failed-registry lifecycle jobs `0`.

Focused lifecycle/auth/RQ regression: 24 passed, 0 failed, 7 warnings, 67.19 seconds.

## Complete Regression

- Backend: 295 collected, 295 passed, 0 failed, 8 warnings, 99.65 seconds.
- Frontend: 8 files and 23 tests passed, 0 failed, 1.60 seconds.
- Frontend production build: PASS (`tsc -b && vite build`).

The backend total increased from 291 to 295 only because the four required deterministic race tests were added.

## Pre- and Post-Gate Readiness

The isolated `rag_recovery_v1` fixture returned HTTP 200 and `status=ready` before the gate, after the gate's normal full-stack restart, and after completion:

- PostgreSQL: OK
- pgvector: `0.5.1`
- Alembic current/expected: `auth_authorization_v1`
- Redis and required workers: OK
- MinIO: OK
- Reconciliation: missing `0`, hash mismatch `0`, orphans `0`
- Deletion ledger: OK
- Ollama: OK
- Model/digest: exact expected values

After Docker Desktop restart, the recovery fixture's default MinIO diagnostic host port fell in a Windows/Hyper-V excluded range. The final-gate-only Compose override used loopback ports 49000/49001; container networking, service behavior, and all persistent volumes were unchanged.

## Complete Product Scenarios

| Scenario | Result |
|---|---:|
| Isolated test identities | PASS |
| Fresh upload → index → retrieve → generate → cite → history | PASS |
| Query during ingestion/indexing | PASS |
| Concurrent duplicate upload | PASS |
| Full-stack Alice/Bob/global authorization isolation | PASS |
| Grounding, abstention, conflict, and citations | PASS |
| Mid-stream auth revocation | PASS |
| Ghost generation/orphan callback protection | PASS |
| Client abort (`CANCELLED` / `CLIENT_CANCELLED`) | PASS |
| Dangling historical citation after source deletion | PASS |
| Document deletion during active ingestion | PASS |
| Account deletion | PASS |
| Account deletion during active ingestion | PASS |
| CSRF/origin, rate limit, stale credentials, direct API | PASS |
| Normal restart, persistence, and non-resurrection | PASS |

Functional, grounding, authorization, lifecycle, and historical invariants all pass.

## Live Deletion-Race Evidence

Document-deletion race:

- Document: `d20e0516-b5d7-4206-a854-8e5228d21181`
- RQ job: `a7d05469-859e-4717-9683-56dea6fc0a96`
- Result: `finished`
- Diagnostic: `PROCESSING_ABORTED_TARGET_DELETED` at `LEGAL_PARSING`
- Final documents/chunks/indexes/active jobs: `0/0/0/0`

Account-deletion race:

- Document: `1440fa04-8ab3-495a-af3e-0da7e492e1ce`
- RQ job: `ef64fa8c-8023-4328-8a80-293abd7bec34`
- Result: `finished`
- Diagnostic: `PROCESSING_ABORTED_TARGET_DELETED` at `PERSISTENCE`
- Final documents/chunks/indexes/active jobs: `0/0/0/0`

Time-bounded application logs contained zero `StaleDataError`, `ForeignKeyViolation`, or `IntegrityError`. The only tracebacks were RQ scheduler Redis disconnects during the gate's intentional full-stack restart; readiness recovered and the restart scenario passed.

The two failed-registry entries from the rejected candidate were intentionally preserved as historical evidence:

- `b9b3a086-c651-4728-a866-5025b47509ab` (ended 05:53:53Z)
- `654c0d9b-5676-4dca-8376-775f5cdb87e7` (ended 05:54:18Z)

The repaired gate began at 08:18:14Z. It added zero failed lifecycle jobs. Both new race jobs are `finished`.

## Findings

- Unexpected server exceptions: `0`
- P0: `0`
- P1: `0`
- P2: `0`
- Storage reconciliation: missing `0`, hash mismatch `0`, orphans `0`
- Late reconstruction/legal-unit/chunk/index side effects after deletion: `0`
- Resurrection after restart: `0`

## Core Change Audit

- Block 1 algorithm changed: NO
- Block 1 lifecycle boundary changed: NO
- Block 2 processing algorithm changed: NO
- Block 2 lifecycle persistence boundary changed: YES
- Block 3 changed: NO
- Block 4 ranking changed: NO
- Block 5 changed: NO
- Block 6 changed: NO
- Production model: `qwen3.5:9b`
- Production prompt: `legal-rag-v2`

## Final Decision

**LEGAL RAG PRODUCT V1 END-TO-END GATE: PASS**

**FINAL PRODUCT V1: READY**
