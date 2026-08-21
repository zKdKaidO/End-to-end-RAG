# Debug UI Phase 02 — Backend schemas

Date: 2026-08-19

- Added strict Pydantic contracts for `DebugRagRequest`, retrieval/context/generation snapshots, `DebugTrace`, evaluation views, chunk detail, and document pipeline views.
- The request accepts only query text, optional document IDs, and an optional evaluation case ID. Retrieval, prompt, model, generation, and context overrides are forbidden.
- Core contracts are typed and reject extra fields.
- Focused schema/artifact/API tests: 10 passed, 0 failed.

Result: PASS.
