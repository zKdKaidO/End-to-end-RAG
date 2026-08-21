# Block 6 Phase 15 — Restart and full regression

Restarted only `postgres` and `api` with `docker compose restart postgres api`; no volumes were deleted.

Post-restart: PostgreSQL healthy, API ready, 10 application tables, 77 `block3-v1` index rows, pgvector 0.5.1, Qwen tokenizer cache PASS, E5 model cache PASS. `/answer` returned HTTP 200 / `COMPLETED` / citation `PASS`; `/answer/stream` emitted start and done without error. The external Ollama model runtime was then explicitly unloaded with `ollama stop qwen3.5:9b`; the next canonical request reloaded it and again returned HTTP 200 / `COMPLETED` / citation `PASS` in 9,731ms.

Final post-restart command: `docker compose exec -e PYTHONPATH=/app -T api python -m pytest tests -v`.

- Collected: 151
- Passed: 151
- Failed: 0
- Skipped: 0
- Warnings: 8
- Duration: 88.15s

Result: PASS.
