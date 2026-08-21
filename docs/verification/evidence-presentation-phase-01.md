# Evidence Presentation Experiment — Phase 01 Pre-flight

Date: 2026-08-20 (Asia/Saigon)

## Frozen dataset integrity

- `evaluation/datasets/legal_eval_v1.json`
  - expected: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`
  - measured: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`
  - result: PASS
- `evaluation/datasets/legal_eval_v2.json`
  - expected: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`
  - measured: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`
  - result: PASS

## Backend baseline

Command: `docker compose exec -e PYTHONPATH=/app api python -m pytest tests -v`

- collected: 230
- passed: 230
- failed: 0
- warnings: 8
- duration: 89.69s

The first attempted run was explicitly discarded because only API/frontend
services had initially been started and the processing-worker integration test
therefore lacked its declared runtime dependency; the run was interrupted. The
record above is the subsequent uninterrupted full-stack run and is the only
pre-flight baseline used by this experiment.

## Frontend baseline

- `npm test -- --run`: 5 files passed, 11 tests passed, 0 failed, 15.23s
- `npm run build`: PASS, 30 modules transformed, 355ms Vite build

## Decision

Pre-flight: **PASS**. Offline experiment implementation may proceed.

