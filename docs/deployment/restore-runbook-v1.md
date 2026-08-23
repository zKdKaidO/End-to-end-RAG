# Destructive restore runbook V1

Restore is guarded by an allowed recovery environment and the exact confirmation token `RESTORE:<BACKUP_ID>`. Stop API/workers and prevent Ollama generation during HNSW rebuild. Preserve the backup, recovery-control ledger, and model cache.

1. Select one `COMPLETE` paired set and run checksum/file-set verification.
2. Start empty PostgreSQL 15 and MinIO targets as required. Fresh PostgreSQL creates pgvector before restore.
3. Run the restore command from the operations profile with the explicit environment, token, and Ollama-stopped acknowledgement.
4. Verify PostgreSQL major, pgvector version, Alembic head, MinIO version, model tag, and model digest.
5. Restore PostgreSQL while deferring exactly `ix_chunk_indexes_embedding`. Restore MinIO, or reuse it only after exact paired-manifest verification.
6. Reconcile stores, revoke every restored auth session, replay post-snapshot account-deletion tombstones, and reconcile durable jobs against Redis.
7. Rebuild HNSW once with bounded `maintenance_work_mem=256MB` and one parallel maintenance worker. GIN and every non-HNSW index are restored normally.
8. Verify the exact model identity and perform final store reconciliation.
9. Start API/workers, require `/ready`, then run authenticated upload/retrieval/generation/citation/history and authorization E2E checks.

Recovery diagnostics are written to `/recovery-control/restore-runs/<BACKUP_ID>` or another explicit control-path output. Do not write into the backup set.
