# Legal-RAG-V3 Final Ablation — Phase 14

Date: 2026-08-22 (Asia/Saigon)

## Final backend regression

Command:

```text
docker compose exec -T -e PYTHONPATH=/app api python -m pytest tests -v
```

Result:

- collected: 235
- passed: 235
- failed: 0
- warnings: 8
- duration: 89.38 seconds

The full pytest process printed its successful terminal summary. As at pre-flight, the host-side Compose wrapper retained an inherited pipe afterward and was stopped after completion; the test result above is the authoritative pytest result.

## Frontend regression and build

```text
npm test
npm run build
```

- Vitest files: 5 passed, 0 failed.
- Vitest tests: 11 passed, 0 failed.
- Vitest duration: 19.06 seconds.
- TypeScript/Vite production build: PASS; 30 modules transformed; build duration 391 ms.

## Final frozen-state checks

- Evaluation V1 SHA-256: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`.
- Evaluation V2 SHA-256: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`.
- Production prompt: `legal-rag-v2`.
- Production behavior changed: NO.
- Blocks 1–5 changed: NO.
- Production database base-table count: 10 (unchanged; zero tables added).
- Schema drift: NONE.
