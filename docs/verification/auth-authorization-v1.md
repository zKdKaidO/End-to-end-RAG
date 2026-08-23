# Auth + Authorization V1 Verification

## Schema and migration

- Current head: `auth_authorization_v1`.
- Exactly six new auth tables: `users`, `auth_sessions`, `document_access_grants`, `global_document_access`, `account_deletion_jobs`, `account_deletion_document_refs`.
- `chat_sessions.user_id` is non-null, indexed, and cascades on user deletion.
- Fresh temporary pgvector database: upgrade to head, downgrade one revision, upgrade to head: PASS. Final table count 6 and `chat_sessions.user_id IS NULLABLE = NO`.
- Existing canonical corpus was backfilled as Global and existing history was assigned to a disabled migration principal.

## Query-plan evidence

The scale transaction inserted 10,000 synthetic Global documents, 500 Alice-private, and 500 Bob-private documents, then rolled back. With the pre-existing corpus this produced 11,321 Global rows and 1,004 private grants during planning.

- Dense: `Index Scan using ix_chunk_indexes_embedding`; authorization executed as hashed subplans; 50 rows; 3.981 ms observed diagnostic execution.
- Lexical: `Bitmap Index Scan using ix_chunk_indexes_lexical_tsv`; access checks used `ix_document_access_document_user` and `global_document_access_pkey`; 36 rows; 1.945 ms.
- No Python authorized UUID materialization and no 10,000-parameter `IN` clause.

These are diagnostic observations, not an SLA. PostgreSQL may select different valid plans as corpus statistics change.

## Security evidence

- Alice canary `CONFIDENTIAL_ALICE_CANARY_8F712A`: zero Bob document API, Dense, Lexical, RRF/final retrieval, Block 5 context, and possible citation evidence occurrences.
- Exact Alice document UUID injected by Bob: 404 before retrieval/generation invocation.
- Cross-user SHA dedup: one canonical row, independent grants.
- Private + Global collision and independent revoke behavior: PASS.
- GC/grant PostgreSQL row-lock race: serialized; grant retained and GC returned false; no dangling reference.
- History GET/PATCH/DELETE/messages IDOR: uniform 404.
- Historical citation snapshot after Global revoke: readable; current chunk: 404.
- USER Debug/Evaluation: 403; ADMIN with enabled flags: allowed.
- Anonymous legacy/stateless retrieval/answer/document/history/internal routes: 401.
- Account deletion: 202; enqueue-gap recovery, shared retention, unique GC, crash/retry, and idempotent completion: PASS.

## Regression

Pre-change baseline was 259 backend tests and 20 frontend tests. Initial baseline required all existing RQ worker services; once the unchanged processing worker was started, it was clean.

- Backend final: 271 collected, 271 passed, 0 failed, 8 warnings, 94.42 s.
- Frontend final: 8 files, 23 tests, 0 failed.
- Frontend production build: PASS (1,821 modules).
- Docker E2E: USER/ADMIN login, Documents, private/global origin lifecycle, real Ollama Ask SSE, persistent History, ADMIN Debug/Evaluation, USER 403, and non-destructive PostgreSQL/API restart: PASS.

Known limitations are the deliberate V1 exclusions documented in the design files. Local development uses a non-Secure cookie only because it is HTTP; production requires `AUTH_COOKIE_SECURE=true` and same-origin TLS.
