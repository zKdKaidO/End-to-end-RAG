# Quality Fix Phase 05 — Full Regression and Runtime Contract

Date: 2026-08-19

Command:

`docker compose exec -T -e PYTHONPATH=/app api python -m pytest tests -v`

Authoritative clean result after all production changes:

- collected: 182
- passed: 182
- failed: 0
- warnings: 8
- duration: 87.58 seconds

The warning set consists of existing framework deprecations and one existing pytest return-value warning.

Real HTTP checks after API restart:

- Non-stream unanswerable response: HTTP 200, `INSUFFICIENT_EVIDENCE`, standardized text, no citations, no internal marker.
- SSE unanswerable response: `start`, `done`; no unsupported delta and no internal marker.
- SSE answerable response: `start`, `delta*`, `done`; valid citation and no internal marker.
- Provider/client cleanup behavior remains covered by regression tests.

Result: PASS.
