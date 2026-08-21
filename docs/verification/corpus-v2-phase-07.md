# Corpus V2 Phase 07 — Final Regression

Date: 2026-08-19

Result: **PASS**.

Backend:

- Collected: 208
- Passed: 208
- Failed: 0
- Warnings: 8
- Duration: 88.34 seconds

Frontend:

- Test files: 5 passed
- Tests: 11 passed, 0 failed
- Production build: PASS, 30 modules transformed

The first expanded-corpus final run exposed one legacy integration test that retrieved the canonical fixture globally and asserted a fixed rank-1 chunk. The test already resolved the canonical document ID but failed to apply it. The assertion was isolated with the existing SQL document pre-filter; no retrieval implementation or production parameter changed. The targeted rerun and complete suite then passed.

Frozen Evaluation V1 SHA-256 remains `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`.
