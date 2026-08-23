# Security Hardening V1 Verification

Date: 2026-08-23 (Asia/Saigon)

## Integrity

- Evaluation V1 SHA-256: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`
- Evaluation V2 SHA-256: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`
- `legal-rag-v2` SHA-256: `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee`
- Production model/prompt: `qwen3.5:9b` / `legal-rag-v2`
- Schema drift: none; new production tables: zero.

## Verification results

- Pre-change baseline: 271 collected, 271 passed, 0 failed, 8 warnings, 96.16 s.
- Focused security suite: 9 passed.
- Frozen auth/API/answer/history focus: 39 passed.
- Isolation canary/scope focus: 2 passed.
- Final backend in API container: 281 collected, 281 passed, 0 failed, 8 warnings, 101.78 s.
- Frontend: 8 files, 23 tests passed, 0 failed.
- Frontend production build: PASS (1,821 modules; 321.35 kB JS, 22.51 kB CSS).
- Docker rebuild: PASS for API, ingestion, processing, indexing and migration images.
- Image secret check: `ENV_ABSENT` for `/app/.env` in `rag-api`.
- Runtime: API health 200; provider health 200; frontend 200.
- API/frontend CSP and `nosniff`: present; local HSTS intentionally off.
- Bindings: API/frontend/Ollama loopback only; no host DB/Redis/MinIO listener.
- Worker egress: internal Redis PASS; public DNS/HTTPS denied.
- Real generation admission: 1/3 admitted, 2/3 rejected, admitted stream completed.
- Real prompt injection: 2/2 safe abstentions, zero leakage/citation fabrication.
- Real account deletion residual probe: PASS; shared data preserved.

## Decision

All 37 hard acceptance properties are satisfied in the defined local deployment capability surface. Security Hardening V1 is ready to freeze, subject to the residual operational requirements in the security documents.
