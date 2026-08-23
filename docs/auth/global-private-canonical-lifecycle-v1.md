# Global / Private Canonical Lifecycle V1

```text
upload bytes
  -> lock/reuse canonical SHA row
  -> create private or Global access reference
  -> invoke frozen ingestion lifecycle

revoke one reference
  -> lock canonical row
  -> delete only requested reference
  -> references remain? retain canonical
  -> zero references? enqueue document-gc

document-gc
  -> lock canonical row
  -> recheck private + Global references
  -> referenced: retain
  -> orphaned: delete MinIO object and canonical aggregate
```

The row lock serializes grant creation and GC. If a grant wins, GC observes it and retains the document. If GC wins, later upload safely recreates/reuses canonical content; the foreign keys prevent a grant from pointing at a missing document.

Global revocation never removes private grants. Private revocation never removes Global access. Deleting a private reference to a still-Global canonical object is a successful private-access removal, and the document remains visible as Global.

MinIO deletion is treated as idempotent. Frozen derived tables continue to use their existing cascades; old non-cascading job/page rows are explicitly removed by the trusted GC worker.
