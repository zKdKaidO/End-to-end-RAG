# Chat Session + Persistent History V1 verification

## Baseline

- Before implementation: backend 245/245 passed, 8 warnings, 92.40 s.
- Before implementation: frontend 7 files / 20 tests passed; production build passed.
- Production remained `qwen3.5:9b` + `legal-rag-v2`.

## Database and migration

- Added revision `chat_session_history_v1`; four tables only.
- Existing populated database upgrade passed.
- Scratch database full upgrade passed after the frozen Block 3 prerequisite `CREATE EXTENSION vector`.
- History downgrade removed all four tables (count 0); re-upgrade restored all four (count 4).
- Verified PostgreSQL named constraints and partial active-turn index with `\d chat_turns`.
- Fresh Alembic without first enabling pgvector fails in the old Block 3 revision; that frozen migration
  was not rewritten. See Known limitations.

## Automated behavior evidence

Real PostgreSQL tests cover request hashing, stable titles, session aggregate cascade, same-key
idempotency, conflict hashing, one-active-turn DB enforcement, orphan recovery/fresh preservation,
insufficient-evidence zero snapshots, injected atomic finalization failure, SSE error/no false done,
keyset pagination, immutable message APIs, session busy deletion, concurrent identical/conflicting/
different-key requests, provider invocation count, document deletion, `SOURCE_UPDATED`, and
UUID-independent `CURRENT_EQUIVALENT`.

The final product-route provider-outage test also verifies persisted `FAILED` state,
`PROVIDER_UNAVAILABLE`, zero snapshots, zero provider generation calls, and SSE `error` without a
false `done` event.

Frontend behavior tests cover session creation/list/open, server reload, rename/delete, message/session
pagination, persistent streaming, cancellation, orphan display, Retry with a new UUID, and snapshot-
primary citation rendering without live chunk fetch.

## Real Docker E2E

Session `994798dd-2992-46c0-be1d-e5fe63d46f1e` used the real RAG pipeline and local model for the
frozen-corpus question about the three social-work regulation topics. It completed with citations
`S2`, `S3`, and `S4`. History contained an identical answer plus three snapshots, each with evidence,
document SHA, chunk-content SHA, provenance, and `CURRENT_EQUIVALENT`.

PostgreSQL and API were restarted without deleting volumes. Reload comparison recorded:

- answer equal: true;
- snapshot count: 3;
- snapshot text equal: true;
- all current states: `CURRENT_EQUIVALENT`.

The same completed client turn ID replayed with `replayed=true`, one persisted turn, three snapshots,
and no new generation. Docker rebuild/recreate also preserved the same history through the volume.

Browser smoke at `http://localhost:5173` passed Ask history, clickable snapshot evidence, Documents,
Debug, and Evaluation. Desktop and 390×844 mobile screenshots are stored beside this report.

## Performance/storage sanity

Five local HTTP samples: session list averaged 5.61 ms (5.07–6.60); history plus three snapshots and
availability resolution averaged 16.50 ms (15.84–17.10). A local service fixture measured turn
initialization 24.907 ms and three-field finalization 17.315 ms. These are diagnostics, not an SLA.

The retained real fixture has 1 session, 1 turn, 2 messages, 3 snapshots, 73.7 average evidence
characters (221 total). After the final regression, PostgreSQL allocated 80/112/112/112 KiB for
sessions/turns/messages/snapshots (416 KiB total), dominated by table/index page overhead from the
create/delete integration fixtures rather than retained payload. ContextPackage rows: 0.

Message history uses select-in bulk loading for turns/snapshots and two bulk current-source queries;
it does not issue one query per citation.

## Final regression

- Backend: 259 collected, 259 passed, 0 failed, 8 warnings, 92.47 s.
- Frontend: 7 test files, 20 tests passed, 0 failed, 2.65 s.
- Frontend production build: passed; 1,820 modules transformed, Vite build 742 ms.
- Final API health: `ok`; retained E2E history: 2 messages, 3 snapshots, all
  `CURRENT_EQUIVALENT`.

## Security/data hygiene

Schema/code inspection found no storage of keys, auth headers, environment, system prompt text,
private reasoning, raw provider payload, full ContextPackage, candidate pools, or DebugTrace. Only
safe failure details and a prompt SHA are retained.

## Known limitations

- No auth/ownership, retention policy, message deletion/editing, branching, sharing, or memory in V1.
- Current-source resolution computes chunk hashes for chunks in same-SHA candidate documents; it is
  deliberately best effort and not fuzzy legal identity matching.
- Fresh databases inherit Block 3's documented requirement that pgvector be enabled before Alembic.
- A hard server crash can lose in-memory partial text; lazy recovery records the interrupted state but
  does not invent output.
