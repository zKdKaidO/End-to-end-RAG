# Abstention Calibration — Phases 35–37

- All experimental prompts remain under `evaluation/experiments/abstention_calibration_v1/`.
- Production `legal-rag-v2` SHA-256 remained `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee`.
- Production Block 6, retrieval, hierarchy retrieval, Block 5, Debug Cockpit, and SSE behavior were not changed.
- Backend regression: **230 collected, 230 passed, 0 failed, 8 warnings in 95.02s**.
- Frontend regression: **11 passed, 0 failed**.
- Frontend production build: **PASS**.
- PostgreSQL public table count remained **10**; no schema operation was performed.

The experiment found no production-eligible prompt. `legal-rag-v2` remains authoritative.

