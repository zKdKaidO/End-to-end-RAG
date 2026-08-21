# Block 4 Phase 06 — Bulk hydration

Status: PASS

Selected final IDs are hydrated with one statement against `chunks`:

```sql
SELECT id, document_id, content_text, metadata_json, provenance_json
FROM chunks
WHERE id = ANY(CAST(:chunk_ids AS uuid[]))
```

The repository test records exactly one execute call for multiple IDs and verifies every output field. The service test deliberately returns hydration rows in reverse insertion order and verifies that application assembly restores exact RRF `final_rank` order.

N+1 queries: NONE.
