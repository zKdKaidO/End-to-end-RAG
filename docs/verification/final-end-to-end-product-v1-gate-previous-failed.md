# Final End-to-End Product V1 Gate

Audit window: 2026-08-24 05:49:24Z–06:01:02Z  
Primary run: `20260824T054924Z-bcbac1`  
Decision: **NOT READY**

The exact release candidate passed functional, grounding, authorization, historical, persistence, storage, and regression checks. It is not ready to freeze because two live deletion races produced release-blocking processing-worker exceptions and left two jobs in the `document-processing` failed registry. No product fix, retry, queue purge, or assertion weakening was performed.

## Release Candidate Identity

Status: **PASS**

- API/workers: `sha256:b5d9acbc4bcaa3e7b62372aedbcd1426bfa68410605ef0a620c32366183ae478`
- Frontend: `sha256:0609b046064912f679fd589cc6563c97b01ce21a0f6c5673eea70273e7e6dc74`
- Model: `qwen3.5:9b`
- Model digest: `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`
- Prompt: `legal-rag-v2`
- Prompt SHA-256: `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee`
- Alembic: `auth_authorization_v1`
- pgvector: `0.5.1`
- Canonical backup: `20260823T161115Z-54300867`

Setup/action: the final production images were run in the isolated `rag_recovery_v1_*` environment through the production TLS edge without source bind mounts. Container inspection after the final restart confirmed the exact image IDs and zero container restart count after startup. The release manifest references the same images.

Expected/actual: exact candidate identity was required and observed. A byte comparison found six host/image auth files differed only by a final blank line; no semantic Core difference exists. No image was rebuilt.

## Pre-Gate Readiness

Status: **PASS**

Setup/action: checked HTTPS frontend and `/api/ready` before scenarios and again after the full-stack restart.

Expected: HTTP 200 with all dependencies, worker queues, model identity, schema, deletion ledger, and reconciliation healthy.

Actual/evidence:

- Frontend HTTP 200 with HSTS.
- API readiness HTTP 200, `status=ready`, no blockers.
- PostgreSQL healthy; pgvector `0.5.1`; current/expected Alembic `auth_authorization_v1`.
- Redis healthy with queues `account-deletion`, `document-gc`, `document-indexing`, `document-processing`, and `ingestion`.
- MinIO and deletion ledger healthy.
- Ollama returned the exact model name/digest.
- Readiness reconciliation: missing `0`, hash mismatch `0`, orphans `0`.

## Fresh User Journey

Status: **PASS**

Setup: created six unique QA identities through the frozen operator provisioning contract. Auth V1 does not expose public self-registration. Passwords and cookies are not recorded. Alice uploaded document `af136ef8-08c3-48dc-aa46-c47f4b8af9eb` containing `ALICE_PRIVATE_SENTINEL_7F92`.

Action: login, `/me`, upload, lifecycle polling, retrieval, a new real Qwen generation, citation open, history read, refresh-equivalent replay, logout, relogin, history reopen, and a second new question.

Expected: a completely new user completes the product journey with grounded new generation, valid citation, persistent history, and correct session behavior.

Actual/evidence: indexing reached `COMPLETED`; retrieval returned the Alice source; the new answer contained the expected 37 percent fact and one citation mapped to Alice's document; logout returned 204; relogin/history succeeded. No prior answer substituted for generation.

## Mid-Ingestion Query

Status: **PASS**

Setup/action: uploaded a generated 350-page PDF (`12f79509-0248-47e9-ae6a-b202302a2a84`) and queried while it was active, then repeated after indexing.

Expected: no inconsistent partial evidence; safe insufficient response while active; normal retrieval/generation when ready.

Actual/evidence: active state had zero chunks/indexes and produced insufficient evidence. After `COMPLETED`, retrieval returned 10 candidates and generation produced the cited 91-day result. No HTTP 500 or hang occurred.

## Concurrent Duplicate Upload

Status: **PASS**

Setup/action: Bob submitted two synchronized uploads of exactly the same bytes.

Expected: frozen SHA-256 deduplication creates one canonical resource and one pipeline.

Actual/evidence: HTTP outcomes were 202/202 and both resolved to `ec613c68-d5b6-438e-9584-5c9ef0a2be79`; DB counts were canonical documents `1`, grants `1`, ingestion jobs `1`, chunks `2`, indexes `2`. Final storage reconciliation found no orphan.

## Authorization Isolation

Status: **PASS**

Setup: Alice, Bob, and global documents used unique private/global sentinels.

Action: tested listings, guessed direct fetch/delete, document-filtered and unfiltered retrieval, generation, citation snapshots, and history in both directions.

Expected: private data never crosses identities; global data remains available.

Actual/evidence: Alice↔Bob direct fetch/delete all returned 404; no private sentinel, evidence text, document ID, citation, or history snapshot crossed the boundary. Global access remained visible. P0 findings: `0`.

## Grounded Generation

Status: **PASS**

Setup/action: exercised strong, weak/incomplete, absent, and conflicting authorized evidence with real `qwen3.5:9b` and `legal-rag-v2`.

Expected: supported claims cite evidence; weak/absent claims abstain; conflict is preserved or conservatively refused.

Actual/evidence: strong evidence was answerable with one valid citation; weak and absent cases returned `INSUFFICIENT_EVIDENCE`; conflict returned `ANSWERABLE`, preserved both 37/41 values, and cited both authorized documents.

## Citation Verification

Status: **PASS**

Setup/action: followed answer citation → History V1 snapshot → original chunk/document → authorization scope for strong and conflict answers.

Expected: no fabricated/wrong source and snapshot content matches evidence used at generation time.

Actual/evidence: the Alice source mapped to document `af136ef8-08c3-48dc-aa46-c47f4b8af9eb`; historical snapshot `35de0949-2de9-4360-bd76-d6bda90bc704` contained the expected evidence. The frozen citation schema uses `current_document_id`/`original_document_id` and both were correct.

## Dangling History

Status: **PASS**

Setup/action: deleted Alice's cited document, waited for GC, reopened old history, attempted direct fetch/retrieval, and made a new generation.

Expected: immutable history snapshot survives while deleted canonical evidence stays dead.

Actual/evidence: the old snapshot remained renderable; document, chunks, and indexes were all `0`; direct API/retrieval could not access it; new generation did not cite or reuse the deleted 37 percent evidence.

## Document Deletion

Status: **PASS** for READY-document data semantics.

Setup/action: the cited READY Alice document was verified, deleted, settled, and checked again after full restart.

Expected: no retrievable semantic footprint or resurrection.

Actual/evidence: DB document/chunk/index counts were zero; direct API and retrieval stayed absent; restart did not resurrect the source. The separate active-ingestion race failed on worker integrity below.

## Delete During Ingestion

Status: **FAIL — P1**

Setup/action: uploaded large document `d0f3e005-b21c-45ca-987a-d558ae30e15f`, confirmed an active lifecycle state, deleted it, then observed workers and persisted state through restart.

Expected: no late write, READY transition, ghost retrieval, endlessly retrying job, or worker exception.

Actual: final document/chunk/index counts were zero, retrieval stayed empty, and there was no resurrection. However processing job `b9b3a086-c651-4728-a866-5025b47509ab` failed while updating a row concurrently removed by deletion.

Exact failure point/evidence:

- `app.repositories.processing_job_repo.update_stage` → SQLAlchemy commit.
- `sqlalchemy.orm.exc.StaleDataError: UPDATE statement on table 'document_processing_jobs' expected to update 1 row(s); 0 were matched.`
- Structured event: `processing_job_failed` at `2026-08-24T05:53:53.680165Z`.
- Request ID: `d29ab8c3-2ece-4cf6-93c1-02cf57fb6ab7`.
- Queue state: retained in the `document-processing` failed registry.

Suspected component: processing-worker deletion-race handling. No system change was made.

## Account Deletion

Status: **PASS** for the settled-account flow.

Setup/action: Alice had authenticated sessions, private documents, retrieval, and history; Bob/global resources were independent. Alice initiated account deletion.

Expected: immediate authorization revocation, Alice cleanup, and Bob/global isolation.

Actual/evidence: Alice user/auth sessions/chat sessions/grants became zero, old credentials returned 401, and private documents/chunks disappeared. Bob retained eight visible documents and global access count remained one. Deleted credentials remained 401 after restart.

## Account Deletion During Ingestion

Status: **FAIL — P1**

Setup/action: account-race user uploaded large document `a57974a2-a35d-4dbf-b1a9-2ac322cef7a9`, confirmed active ingestion, then deleted the account and observed workers/state through restart.

Expected: revocation and cleanup without late writes, DB exceptions, poisoned jobs, or resurrection.

Actual: user/document/chunk/index cleanup, authorization revocation, and non-resurrection passed. Processing nevertheless attempted a late `document_reconstructions` insert after the document row was deleted.

Exact failure point/evidence:

- `app.repositories.processing_repo.save_processing_results` → `document_reconstructions` INSERT.
- `psycopg2.errors.ForeignKeyViolation`, surfaced as `sqlalchemy.exc.IntegrityError`.
- Processing job: `654c0d9b-5676-4dca-8376-775f5cdb87e7`.
- Structured event: `processing_job_failed` at `2026-08-24T05:54:18.223583Z`.
- Request ID: `6fef902c-3ece-4cf6-93c1-02cf57fb6ab7`.
- Queue state: retained in the `document-processing` failed registry.

Suspected component: processing-worker account-deletion race handling. No system change was made.

## Mid-Stream Auth Revocation

Status: **PASS**

Setup/action: started an authenticated stream and logged out after the server accepted it.

Expected: frozen request-start authorization allows the accepted stream to settle; every new request is rejected and history is terminal.

Actual/evidence: stream HTTP 200, logout HTTP 204, turn `COMPLETED`, and new requests were unauthorized. No infinite state or inconsistent partial completion was observed.

## Ghost Generation

Status: **PASS**

Setup/action: deleted a chat while a generation stream was active.

Expected: late output cannot recreate the session or persist an orphan completed answer.

Actual/evidence: deletion returned 204; final DB counts were sessions `0`, completed turns `0`. No ghost row was observed.

## Client Abort

Status: **PASS**

Setup/action: closed the SSE client immediately after the authoritative `start` event.

Expected: no incorrectly completed history or orphan transaction.

Actual/evidence: persisted state was `CANCELLED` with `CLIENT_CANCELLED`; no `done` event was consumed. This is the frozen terminal disconnect contract.

## Restart Persistence

Status: **PASS**

Setup/action: restarted the complete isolated stack without deleting/restoring volumes, then exercised frontend, readiness, login, documents, retrieval, a new generation, citations, and history.

Expected: live state and runtime capability persist.

Actual/evidence: readiness returned HTTP 200; Bob's live document retrieved one expected result; a new post-restart answer was `ANSWERABLE` with citation; prior history remained readable.

## Resurrection Checks

Status: **PASS** for persisted data state.

Setup/action: checked deleted document and deleted-account resources before and after the normal restart.

Expected: no deleted resource returns through stale jobs, retry queues, reconciliation, or restart hooks.

Actual/evidence: deleted document APIs/retrieval remained absent and deleted account logins returned `[401, 401]`. The two failed processing jobs did not resurrect data, but their exceptions remain P1 blockers.

## Security Mitigation / Rate Limit / CSRF

Status: **PASS**

Setup/action: used realistic browser cadence for normal flows, then ran a separate deliberate invalid-login burst and a missing-Origin mutation.

Expected: legitimate traffic works; adversarial requests fail controllably.

Actual/evidence: normal flows had no 403/429. Missing Origin returned 403. Seven deliberate invalid logins returned 401 and the eighth returned 429 with `Retry-After: 4`. Deleted credentials returned 401. Security controls were not disabled.

## Direct API Adversarial Checks

Status: **PASS**

Setup/action: cross-user fetch/delete, cross-user retrieval/history, stale deleted credentials, and invalid mutation Origin were exercised.

Expected: controlled 401/403/404 and never 500.

Actual/evidence: cross-user resource operations returned 404, missing Origin returned 403, stale credentials returned 401, and no API 500 occurred.

## Log Integrity

Status: **FAIL — P1**

Setup/action: inspected API, ingestion, processing, indexing, PostgreSQL, Redis, MinIO, and edge logs from `2026-08-24T05:49:24Z` onward for tracebacks, integrity errors, unexpected 500s, crashes, and retry storms.

Expected: no unexpected server/worker exception.

Actual/evidence: API 500 count was zero and no container crash/restart occurred after restart startup. Two unexpected processing-worker error events correspond exactly to the two deletion-race findings above. Redis connection-refused tracebacks during the deliberate full-stack restart were classified as expected shutdown ordering, followed by healthy worker restart; they are not release findings.

Unexpected server/worker exception events: **2**.

## Queue Quiescence

Status: **FAIL — P1**

Setup/action: inspected RQ queues and registries through the exact candidate API after all scenarios and restart.

Expected: no queued/started work, no retry storm, required workers alive, and no failed deleted-resource jobs.

Actual/evidence:

| Queue | Queued | Started | Deferred | Scheduled | Failed |
|---|---:|---:|---:|---:|---:|
| ingestion | 0 | 0 | 0 | 0 | 0 |
| document-processing | 0 | 0 | 0 | 0 | 2 |
| document-indexing | 0 | 0 | 0 | 0 | 0 |
| document-gc | 0 | 0 | 0 | 0 | 0 |
| account-deletion | 0 | 0 | 0 | 0 | 0 |

Workers were alive/idle and there was no retry storm. The two retained failed jobs are the two P1 findings; audit policy forbids clearing them.

## Storage Reconciliation

Status: **PASS**

Setup/action: ran non-destructive `reconcile-store` after all scenarios.

Expected: zero missing objects, hash mismatches, and unexpected orphans.

Actual/evidence: expected `26`, present `26`, missing `0`, hash mismatch `0`, orphan `0`, readiness blocked `false`; verified at `2026-08-24T05:57:10.959851Z`. No repair action ran.

## Regression

Status: **PASS**

No tests were modified, skipped, or weakened.

- Backend: `291 collected`, `291 passed`, `0 failed`, `8 warnings`, `102.32s`.
- Frontend: `8 files`, `23 tests`, `23 passed`, `0 failed`, `16.69s`.
- Frontend production build: **PASS** (`vite v8.2.1`, 1821 modules, 760ms build step).

## Artifact Consistency

Status: **PASS**

Setup/action: rechecked running image IDs, release manifest, model digest, prompt file hash, readiness schema/version, backup evidence, and targeted semantic Core diff.

Expected: the gated image remains the exact frozen candidate.

Actual/evidence: all expected image/model/prompt/schema values match. `deployment/release-manifest.json` references the exact images. The recovery JSON references backup `20260823T161115Z-54300867`. Blocks 1–6 have no semantic audit mutation. The E2E TLS/compose override and runner are test-only under `evaluation/e2e/`.

Auditor-only harness corrections were transparently isolated: frozen History V1 citation field mapping, rate-window scheduling for the disconnect probe, immediate close at SSE `start`, and acceptance of the exact `CANCELLED/CLIENT_CANCELLED` terminal contract. None changed product code or weakened product assertions.

## Findings

### P1 — document deletion during active processing

- Expected: worker observes deletion/tombstone without exception.
- Actual: stage update attempted after the processing-job row disappeared.
- Failure: `StaleDataError` → `DatabaseError`.
- DB/object outcome: clean; no resurrection.
- Queue outcome: failed job retained.
- Reproduce: upload large PDF → confirm active → delete document → settle → inspect `document-processing` failed registry and processing-worker logs.

### P1 — account deletion during active processing

- Expected: worker observes account/document deletion without late write or exception.
- Actual: late reconstruction INSERT referenced an already deleted document.
- Failure: `ForeignKeyViolation` / `IntegrityError`.
- DB/object outcome: clean; no resurrection.
- Queue outcome: failed job retained.
- Reproduce: upload large private PDF → confirm active → delete owner account → settle → inspect registry/logs.

Finding counts: P0 `0`, P1 `2`, P2 `0`, P3 `0`.

## Final Decision

**NOT READY**

The exact candidate is functionally usable and preserved all tested security/privacy boundaries, but Product V1 must not freeze with unresolved P1 lifecycle failures. The engineering cycle must reopen for the processing-worker deletion races; afterward a new release candidate requires regression and the entire Final Product V1 Gate rerun.

Machine-readable evidence: `evaluation/e2e/final_product_v1_gate.json`.
