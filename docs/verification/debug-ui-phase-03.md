# Debug UI Phase 03 — Debug orchestrator

Date: 2026-08-19

- `DebugRagService` calls the frozen `AnswerService.prepare` and `stream_prepared` path.
- Request-scoped capture wrappers observe the real frozen retrieval repository/service, real `ContextPackage`, and real `GenerationResult`.
- No trace is written to PostgreSQL, Redis, disk, or another persistence layer.
- Candidate previews are hydrated in one read-only bulk query; final context is not reselected or retokenized.
- Runtime checks covered a normal query, a document-filtered query, an evaluation rerun, and a zero-evidence short circuit.

Result: PASS.
