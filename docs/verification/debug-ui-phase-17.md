# Debug UI Phase 17 — Restart

Date: 2026-08-19

Restarted only API and frontend services with `docker compose restart api frontend`. No volume was deleted.

Persistence checks before and after restart:

- Documents: 629 → 629
- Chunks: 2781 → 2781
- Chunk indexes: 1504 → 1504
- Public database tables: 10
- Frozen dataset hash remained `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`.

Post-restart runtime checks:

- Frontend `/debug`: HTTP 200.
- Evaluation summary: `legal_eval_v1` loaded.
- Provider: available, `qwen3.5:9b`.
- Real Debug: dense 50, lexical 1 (`SELECTIVE_FALLBACK`), final 10, selected 10, context 1488/4096, `COMPLETED`, `ANSWERABLE`, 2 citations.
- Real Ask SSE: HTTP 200; start 1, delta 101, done 1, error 0; completed result and citation present.

Result: PASS.
