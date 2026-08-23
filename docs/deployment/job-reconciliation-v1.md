# Redis and durable-job reconciliation V1

Redis is not part of the business backup. Durable database job rows drive recovery.

| Durable work | Queue | Recovery rule |
|---|---|---|
| ingestion | `ingestion` | missing PENDING work is requeued; stale non-idempotent PROCESSING work is failed explicitly |
| legal processing | `document-processing` | same rule |
| indexing | `document-indexing` | same rule; operator/API can create an explicit retry |
| account deletion | `account-deletion` | idempotent intent is requeued, including stale RUNNING work |
| orphan document GC | `document-gc` | inferred from durable access state and normal GC paths |

RQ presence is not automatically treated as live. A stale job left in `StartedJobRegistry` after worker loss is removed before the DB-driven decision. Results are retained for 24 hours and failures for 7 days by default; this is diagnostics retention, not durability.

History V1 stale-turn recovery remains unchanged and is reported separately. Reconciliation never runs duplicate retry loops or depends on a Redis backup.
