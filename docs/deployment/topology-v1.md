# Single-node deployment topology V1

The supported production topology is `deployment/docker-compose.production.yml`. `edge` is the only public ingress. It terminates TLS, redirects HTTP to HTTPS, applies security headers, serves the frontend, and proxies same-origin `/api/` traffic. PostgreSQL, Redis, MinIO, API workers, and Ollama have no host-published ports and communicate on internal Docker networks.

Startup order is PostgreSQL/Redis/MinIO/Ollama, one-shot `db-migrate`, API and workers, frontend, then edge. The migration job runs deployment preflight, `alembic upgrade head`, and a head check before application services can start.

Persistent state is deliberately separated:

| State | Production mount | Backup treatment |
|---|---|---|
| PostgreSQL 15 / pgvector 0.5.1 | `postgres_data` | Custom-format PostgreSQL 15 dump |
| MinIO source PDFs | `minio_data` | Object mirror paired with the DB dump |
| Ollama model | explicit host model path | Provisioned separately; exact digest recorded |
| Hugging Face embedding cache | `model_cache` | Provisioned separately; mounted by API/indexer |
| Redis/RQ | ephemeral Redis state | Not backed up; reconstructed from durable DB jobs |
| Deletion tombstones | external recovery-control path | Must survive business-store loss |
| Backup sets | external protected backup path | Must be encrypted and a separate failure domain in production |

This is a single-node design. It does not claim HA, PITR, or zero-downtime database migration.
