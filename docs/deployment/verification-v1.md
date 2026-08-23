# Deployment, backup, and recovery verification V1

The drill used only named volumes prefixed `rag_recovery_v1_`; production/dev volumes were never destructive targets. Exact confirmation tokens and volume-name guards were required.

Observed matrix:

| Test | Result | Key evidence |
|---|---|---|
| A restart persistence | PASS | authenticated scoped retrieval/generation/history passed after normal restart |
| B Redis loss | PASS | durable PENDING indexing job requeued and completed |
| C PostgreSQL loss | PASS | 152 vectors restored; surviving MinIO accepted only as exact pair |
| D MinIO loss | PASS | 2 objects / 664,037 bytes restored from paired set |
| E both stores lost | PASS | paired restore and final hash reconciliation passed |
| F missing object | PASS | `missing_count=1`, readiness blocked; exact repair cleared it |
| G orphan object | PASS | `orphan_count=1`, reported without destructive cleanup |
| H hash corruption | PASS | `hash_mismatch_count=1`, readiness blocked; exact repair cleared it |
| I HNSW restore | PASS | exactly one HNSW TOC entry deferred and rebuilt once; 152 vectors present |
| J model loss | PASS | isolated empty model directory produced `MODEL_NOT_PROVISIONED` |
| K session resurrection | PASS | cookie present in restored snapshot rejected with HTTP 401 |
| L deletion resurrection | PASS | post-snapshot tombstone replay left deleted account absent; HTTP 401 |

The clean PostgreSQL-15 backup `20260823T161115Z-54300867` completed in 0.475 seconds and passed immutable file-set/checksum verification again after all drills. Core restore work was observed at 0.773–1.179 seconds for the 2-document fixture; full service orchestration reached readiness in roughly 47–53 seconds. HNSW rebuild itself was observed at 0.018–0.026 seconds with `maintenance_work_mem=256MB`, one maintenance worker, and Ollama stopped. These are small local observations, not production SLAs.

Final regression gates were 291/291 backend tests, 23/23 frontend tests across 8 files, and a successful frontend production build. The machine-readable record is `evaluation/recovery/deployment_recovery_v1.json`.
