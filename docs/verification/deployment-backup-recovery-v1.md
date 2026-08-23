# Deployment + Backup + Recovery V1 verification

- Frozen Evaluation V1 SHA-256: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`
- Frozen Evaluation V2 SHA-256: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`
- `legal-rag-v2` SHA-256: `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee`
- PostgreSQL: 15.19
- pgvector: 0.5.1
- Alembic: `auth_authorization_v1`
- production model: `qwen3.5:9b`
- verified model digest: `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`
- production prompt: `legal-rag-v2`
- new production tables: 0

Fresh bootstrap, paired backup/checksum verification, cross-store barrier, Redis reconciliation, PostgreSQL-only/MinIO-only/paired restore, exact HNSW deferral/rebuild, reconciliation failure injection, model fail-closed, restored-session revocation, deletion-tombstone replay, and post-restore product E2E all passed in the isolated recovery project.

Final verification:

- backend: 291 collected, 291 passed, 0 failed, 8 warnings, 100.16 seconds;
- frontend: 8 test files passed, 23 tests passed, 0 failed, 18.78 seconds;
- frontend production build: PASS;
- development, production, and isolated-recovery Compose configuration: PASS;
- immutable clean backup re-verification after all drills: PASS;
- production/dev volumes targeted by destructive commands: NONE.

The authoritative machine-readable evidence is `evaluation/recovery/deployment_recovery_v1.json`; the operator-facing matrix and timing scope are in `docs/deployment/verification-v1.md`.
