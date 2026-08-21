# Hierarchy V2 Phase 38 — Full Regression

Status: **PASS**

Backend command: `docker compose exec -e PYTHONPATH=/app api python -m pytest tests -v`

- collected: 230
- passed: 230
- failed: 0
- warnings: 8
- duration: 90.91 seconds (`-v`)

After the final candidate-immutability contract flag was applied, the complete 230-test suite ran again: 230 passed, 0 failed, 8 warnings, 90.34 seconds.

Frontend:

- test files: 5 passed
- tests: 11 passed, 0 failed
- production build: PASS
- modules transformed: 30
- build duration: 149 ms
