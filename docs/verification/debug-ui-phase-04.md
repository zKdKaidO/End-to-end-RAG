# Debug UI Phase 04 — Internal debug routes

Date: 2026-08-19

Implemented development-only routes:

- `GET /internal/debug/status`
- `POST /internal/debug/rag`
- `GET /internal/debug/chunks/{chunk_id}`
- `GET /internal/debug/documents`
- `GET /internal/debug/documents/{document_id}`

`DEBUG_UI_ENABLED` and a development/local/test `APP_ENV` are both required; disabled routes return 404. Tests verify that request/model/prompt overrides are rejected and that responses exclude system prompts, reasoning traces, authorization data, and secrets.

Result: PASS.
