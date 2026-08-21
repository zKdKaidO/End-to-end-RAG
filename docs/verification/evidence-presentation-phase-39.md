# Evidence Presentation Experiment — Phase 39 Regression

## Backend

Command: `docker compose exec -e PYTHONPATH=/app api python -m pytest tests -v`

- collected: 235
- passed: 235
- failed: 0
- warnings: 8
- duration: 88.72s

The five additional tests are isolated experiment-utility tests. All 230 prior
core/evaluation/debug tests remain included and green.

## Frontend

- test files: 5 passed
- tests: 11 passed
- failed: 0
- duration: 1.11s
- build: PASS
- build modules: 30
- Vite build duration: 143ms

## Frozen-state audit after regression

- Evaluation V1 SHA: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`
- Evaluation V2 SHA: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`
- legal-rag-v2 SHA: `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee`
- PostgreSQL public tables: 10 (unchanged)
- production fingerprint comparison: all overlapping frozen files match the
  preceding abstention-calibration experiment exactly

Result: **PASS**.

