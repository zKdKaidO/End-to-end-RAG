# Account-deletion disaster recovery V1

An account-deletion request commits its durable DB intent, appends an idempotent tombstone to the external recovery-control ledger, and only then enqueues RQ work. If the ledger is unavailable the API fails safely with a 503 after protecting the durable intent; startup reconciliation backfills/records the tombstone before queueing.

The ledger contains subject UUID, deletion-job UUID, request time, and format version—no email or password. It must live outside PostgreSQL/MinIO and survive restoration of an older business snapshot.

Restore revokes sessions, selects tombstones newer than the backup snapshot, recreates missing deletion intent, and executes the existing idempotent deletion worker synchronously before readiness. The destructive drill backed up Alice, deleted Alice after the snapshot, destroyed both business stores, restored the older snapshot, and verified Alice remained absent and login returned 401.
