# Upgrade and rollback V1

Each release records a release ID, source commit when available, Alembic head, PostgreSQL/pgvector/Redis/MinIO versions, frontend build hash, and exact model identity. Deployment runs preflight and migrations as a one-shot gate before API/worker startup.

Before upgrade, create and verify a paired backup and export the release manifest. Apply only migrations reviewed for the deployed PostgreSQL major. This V1 introduces no new production tables and no schema migration.

Application rollback is allowed only while the old binary supports the current schema. Database rollback uses the paired restore runbook rather than ad-hoc Alembic downgrade. A restore requires an exactly compatible Alembic revision, PostgreSQL major, pgvector extension, MinIO format pin, and model identity. Unsupported combinations stop before application traffic.
