# Paired backup contract V1

A backup set has one immutable `BACKUP_ID` and contains a PostgreSQL 15 custom archive, a MinIO object mirror, object manifest, reconciliation report, manifest, SHA-256 list, and a `COMPLETE` marker written last. `COMPLETE` is the eligibility boundary. An incomplete set is retained for diagnosis but cannot be restored normally.

Backup uses an exclusive PostgreSQL advisory lock shared with upload, account deletion, and document GC mutations. This gives the DB dump and MinIO mirror one coordinated application-level snapshot. Before completion, reconciliation hashes every canonical `<document_id>/original.pdf` object against `documents.sha256`. Missing or corrupt objects abort the backup; orphans are reported.

Both archive creation and restore use PostgreSQL 15 tools pinned in the application image. Verification rejects a checksum mismatch, missing metadata, incompatible format, or any file added after completion. Restore diagnostics are written under recovery control, never into the immutable set.

Commands:

```text
python -m app.deployment.cli backup-create --root /backups
python -m app.deployment.cli backup-verify --root /backups --backup-id <ID>
python -m app.deployment.cli backup-retention --root /backups
```

Retention is whole-set only: keep the latest 7 and sets newer than 30 days by default. Deletion is dry-run unless explicitly applied. Scheduling remains an operator/platform concern in V1; the repository does not pretend a manual schedule provides a fixed production RPO.
