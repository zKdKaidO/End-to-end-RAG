# Targeted RAG Quality Fixes V1 — Phase 01 Pre-flight

Frozen evaluation dataset:

- path: `evaluation/datasets/legal_eval_v1.json`
- SHA-256: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`
- expected SHA-256: identical
- result: PASS

Baseline command:

`docker compose exec -e PYTHONPATH=/app -T api python -m pytest tests -v`

Baseline result:

- collected: 168
- passed: 168
- failed: 0
- warnings: 8
- duration: 88.70 seconds

No production changes preceded this verification.

Result: PASS.
