# Chat Session + Persistent History V1 — implementation map

This map records the repository audit completed before production code was changed.

| Concern | Existing implementation | V1 integration point |
|---|---|---|
| Database | Synchronous SQLAlchemy `SessionLocal` in `app/db/database.py`; PostgreSQL through psycopg2 | Add isolated `app/chat` service/repository over the same request-scoped session |
| Models | Declarative `Base`; UUID primary keys; PostgreSQL JSON/UUID types | Add exactly four history aggregate models and import them from `app/models/__init__.py` |
| Migrations | Linear Alembic revisions under `app/db/migrations/versions` | Add one revision after `block_3_indexing_models`; no old revision rewrite |
| Transactions | Repositories currently commit directly | Chat service owns explicit initialization, terminal-state, and atomic finalization transactions |
| Generation | `AnswerService.prepare()` and `stream_prepared()` wrap Blocks 4–6 | Product stream calls those reusable methods directly; stateless `/answer/stream` remains intact |
| Valid citations | `GenerationResult.citations` contains only citations accepted by `validate_and_map_citations` | Intersect validated source IDs with `PreparedAnswer.package.selected_evidence`; snapshot only that evidence |
| Citation provenance | Selected evidence carries exact content, metadata, provenance, chunk/document/legal-unit IDs | Store immutable evidence text and hashes; never FK snapshots to live source tables |
| Request IDs | Middleware creates/propagates `request.state.request_id` | Persist only safe correlation metadata and use it in structured logs |
| Document lifecycle | Documents cascade to pages/legal units/chunks/indexes | Snapshot identifiers are soft UUID values, so source cascades cannot reach history |
| Frontend Ask | `/ask` uses the stateless SSE client, buffered deltas, AbortController, and source drawer | Add a compact session rail and product SSE client while preserving the workspace and coalescing hook |
| Frontend data | Typed API helpers in `frontend/src/api/client.ts`; server remains authoritative | Add typed session/message/snapshot contracts; no history in localStorage |
| SSE | Existing `start`, `delta`, `done`, `error`; upstream closes on disconnect | Preserve event names; add IDs/replay flag in `start`; commit history before `done` |
| Pagination | No chat API exists | Opaque keyset cursor for sessions; `before_sequence` keyset for messages |
| Runtime | API container mounts existing code and model cache; Alembic migrate service gates startup | Existing compose workflow applies the new migration; no service/table beyond the four history tables |

Frozen boundaries: retrieval, context selection, generation profile/model/prompt, status parser,
citation parser, debug/evaluation APIs, and stateless answer APIs are not changed.
