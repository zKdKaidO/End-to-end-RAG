# Liveness and readiness V1

`GET /health` and `GET /live` are process liveness checks. They must not depend on downstream services.

`GET /ready` is a dependency/compatibility gate. It checks deployment configuration, recovery-mode flag, PostgreSQL connectivity, pgvector version, Alembic head, Redis and required worker queues in production, MinIO, exact Ollama model identity, latest cross-store blockers, and deletion-ledger availability. It returns HTTP 503 with controlled blocker codes when unsafe.

Missing or hash-mismatched canonical objects block readiness. Orphan objects are reported for operator review but do not automatically block or delete data. Model absence/mismatch, migration drift, vector-extension absence, or active recovery mode block readiness.

The edge proxy routes traffic only after the API healthcheck has passed. Readiness contains no secrets, embeddings, document text, or raw query data.
