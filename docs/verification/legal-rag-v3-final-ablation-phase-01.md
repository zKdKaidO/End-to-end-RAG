# Legal-RAG-V3 Final Ablation — Phase 01

Date: 2026-08-22 (Asia/Saigon)

## Frozen dataset verification

- `evaluation/datasets/legal_eval_v1.json`: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`
- `evaluation/datasets/legal_eval_v2.json`: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`
- Result: PASS; both hashes equal the frozen contracts.

## Pre-flight backend regression

Command:

```text
docker compose exec -e PYTHONPATH=/app api python -m pytest tests -v
```

Result:

- collected: 235
- passed: 235
- failed: 0
- warnings: 8
- duration: 93.86 seconds

The pytest summary completed successfully. The host-side `docker compose exec` wrapper retained an inherited service pipe after pytest exited and was stopped only after the complete summary was captured; this did not interrupt the test process or change its result.

Production prompt at pre-flight: `legal-rag-v2`.
