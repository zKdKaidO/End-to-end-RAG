# Multi-Evidence Phase 28 — Full Regression

Status: **PASS**

Backend command:

`docker compose exec -T -e PYTHONPATH=/app api python -m pytest tests -v`

- Collected: 212
- Passed: 212
- Failed: 0
- Warnings: 8
- Duration: 91.03 seconds

The count includes 208 pre-existing backend tests plus four deterministic experiment tests.

Frontend commands:

- `npm test -- --run`: 5 files, 11 tests passed, 0 failed, 1.21 seconds.
- `npm run build`: PASS; 30 modules transformed; Vite build 125 ms.

Frozen dataset SHA-256 checks after the experiment:

- Evaluation V2: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`
- Evaluation V1: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`

Schema/isolation:

- Public PostgreSQL table count: 10 (unchanged).
- Production imports of `evaluation.experiments.multi_evidence_v1`: 0.
- New production database tables: 0.
- Redis/RQ changes: none.

