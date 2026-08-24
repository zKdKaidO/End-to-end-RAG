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

## Final deliverable image verification

Verified at `2026-08-24T04:55:49.0431956Z`. The final production image identities are API/workers `sha256:b5d9acbc4bcaa3e7b62372aedbcd1426bfa68410605ef0a620c32366183ae478` and frontend `sha256:0609b046064912f679fd589cc6563c97b01ce21a0f6c5673eea70273e7e6dc74`. The isolated verification containers run API/workers `sha256:cc979f99ff7463485dc5ea8c293348fa3f464a2299024a17ade8fac723350bbc` and recovery-endpoint frontend `sha256:e350429c656fa28d1f89a54f2e621d4f660900202dc0e260e12defbb087c0fdf`.

All six `rag_recovery_v1_*` persistent volumes remained present. After the local Docker engine restarted, the existing containers were started in place; no recreate, restore, or destructive drill was repeated. Isolated `/ready` returned HTTP 200 with Alembic `auth_authorization_v1`, pgvector `0.5.1`, all five required worker queues, MinIO, deletion ledger, and exact `qwen3.5:9b` digest healthy. Reconciliation was `missing=0`, `hash_mismatch=0`, `orphans=0`.

The final small smoke passed frontend HTTP, controlled login, `/api/v1/auth/me`, documents, persistent History, one authorized document-filtered retrieval (3 results), and admin/Bob private-document isolation. Temporary smoke credential hashes were restored and both sessions logged out. Generation reused the already verified real-model E2E because generation code and images were unchanged.

Final artifact consistency passed: both JSON artifacts parse, the release image IDs exist locally, the running Alembic/model identities match the manifest, and `legal-rag-v2` still hashes to `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee`. Canonical backup `20260823T161115Z-54300867` again returned `BACKUP_INTEGRITY_VERIFIED`; its completed file set and checksums were unchanged.
