# Debug UI Phase 18 — Final full regression

Date: 2026-08-19

Final backend command:

`docker compose exec -T -e PYTHONPATH=/app api python -m pytest tests -v`

- Backend collected: 192
- Backend passed: 192
- Backend failed: 0
- Backend warnings: 8
- Backend duration: 89.08 seconds

Final frontend verification:

- Test files: 5 passed
- Tests passed: 10
- Tests failed: 0
- Test duration: 905 ms
- TypeScript check: PASS
- Vite production build: PASS
- Modules transformed: 30
- JavaScript bundle: 260.74 kB (80.97 kB gzip)
- CSS bundle: 8.25 kB (2.69 kB gzip)
- Container production build/recreation: PASS
- Final frontend HTTP check: 200

Frozen dataset SHA-256 remained `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`. Database schema remained the same 10 public tables.

Result: PASS.
