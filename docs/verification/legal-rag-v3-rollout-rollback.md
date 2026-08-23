# Legal-RAG-V3 Rollout/Rollback Rehearsal

Date: 2026-08-22

## Controlled V3 selection

A temporary API container was started with the existing server-owned configuration mechanism:

`GENERATION_PROMPT_VERSION=legal-rag-v3`

- `/health`: HTTP 200, `status=ok`.
- `/answer`: HTTP 200, `prompt_version=legal-rag-v3`, `COMPLETED`, `ANSWERABLE`, three citations, no internal marker leakage.
- `/answer/stream`: HTTP 200; one `start`, 94 `delta`, one `done`, zero `error`; start/done identified V3 and no marker leaked.

## Rollback

The exact temporary V3 container was stopped. The existing API continued with the repository/default V2 selection:

- `/health`: HTTP 200, `status=ok`.
- `/answer`: HTTP 200, `prompt_version=legal-rag-v2`, `COMPLETED`, `ANSWERABLE`, three citations, no marker leakage.
- `/answer/stream`: HTTP 200; one `start`, 101 `delta`, one `done`, zero `error`; V2 reported and no marker leaked.
- V2 SHA remained `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee`.

Rollback required no database migration, reindex, frontend rebuild, schema action, or dataset change. Final active/default version: `legal-rag-v2`.
