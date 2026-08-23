# Deployment Implementation Map V1

This map records the repository before Deployment + Backup + Recovery V1 implementation.

## Runtime topology

- `docker-compose.yml` is the local HTTP stack. It has PostgreSQL, Redis, MinIO, one-shot `migrate`, FastAPI `api`, nginx `frontend`, ingestion/account-deletion/document-GC `worker`, `processing-worker`, and `indexing-worker`.
- PostgreSQL uses `postgres/Dockerfile`, based on PostgreSQL 15 Alpine with pgvector 0.5.1 compiled into the image. The image contains the extension files but no `docker-entrypoint-initdb.d` SQL, so extension creation currently depends on migrations/manual state.
- Alembic configuration is `alembic.ini` plus `app/db/migrations/env.py`. Current migration chain ends at `chat_session_history_v1`; `migrate` runs `alembic upgrade head` once and API/workers depend on successful completion.
- API and frontend bind loopback for local development. PostgreSQL, Redis, and MinIO are on Docker network `backend`, marked internal; API also uses `provider` to reach host Ollama. Workers have memory/CPU/PID bounds.
- Persistent named volumes are `postgres_data`, `redis_data`, `minio_data`, and Hugging Face `model_cache`. Host Ollama persistence is currently external to Compose.

## Persistent business data

- PostgreSQL contains canonical documents, pages, legal units, chunks, vector/index rows, ingestion/processing/indexing jobs, grants/global access, users/session hashes, chat history and citation snapshots, and durable account-deletion jobs/refs.
- MinIO bucket defaults to `documents`; canonical key is `<document_id>/original.pdf`, with URI `minio://<bucket>/<document_id>/original.pdf`.
- Redis contains RQ runtime state, rate limits and generation leases. It does not contain canonical source/chat/account data.
- Physical HNSW index is `ix_chunk_indexes_embedding`; vector rows remain PostgreSQL business data. GIN is not singled out for deferral.

## Queue durability

| Queue | Durable intent | Current recovery behavior | Gap before V1 |
|---|---|---|---|
| `ingestion` | `ingestion_jobs` + document/object | RQ retry only | no DB/RQ reconciliation after Redis loss |
| `document-processing` | `document_processing_jobs` + pages | RQ retry only | no DB/RQ reconciliation |
| `document-indexing` | `indexing_jobs` + chunks | RQ retry only | no DB/RQ reconciliation |
| `account-deletion` | `account_deletion_jobs` + refs | startup re-enqueues PENDING/FAILED | no external post-backup deletion ledger |
| `document-gc` | inferred from absence of grants/global access | startup scans orphans | no backup mutation barrier |

History stale PENDING/STREAMING recovery is owned by `ChatHistoryService` and `ORPHANED_STREAM_TIMEOUT`; Deployment V1 must not replace it.

## Existing health/config/recovery

- `/health` is process liveness. `/ready` currently returns ready without checking dependencies, migration head, model identity, reconciliation, or recovery mode.
- Pydantic settings read `.env`. Security V1 removed fallback database/MinIO secrets, but no production-profile fail-fast contract exists yet.
- No paired PostgreSQL/MinIO backup, manifest, checksum, restore, reconciliation, release manifest, model provisioning, retention, or destructive recovery harness exists.
- Account deletion performs MinIO and PostgreSQL mutations but has no external deletion tombstone. Cross-store upload/deletion operations have no backup barrier.

## Frozen boundaries

Deployment V1 will add only deployment/configuration, health/readiness, barrier, backup/restore, reconciliation and recovery controls. It will not change ingestion parsing, legal processing, embeddings, retrieval ranking/fusion/hierarchy, context selection, generation prompt/model/status/citation, authorization predicates, or History citation snapshots.
