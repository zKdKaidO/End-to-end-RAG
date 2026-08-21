# Block 4 Phase 08 — Document pre-filter

Status: PASS

Live verification used two distinct indexed documents:

- A: `89eebb70-2020-45c0-a6f0-44d292f4a49b` (`sample_legal.pdf`);
- B: `1efc75bf-e911-4f1e-963f-14397dee69cb`.

Retrieval was executed with `document_ids=[A]`:

- dense candidates: 100% document A;
- lexical candidates: 100% document A;
- fused/final candidates: 100% document A.

Repository tests inspect both generated SQL paths and require:

```sql
ci.document_id = ANY(CAST(:document_ids AS uuid[]))
```

No Python post-filter exists. A nonexistent document filter returned zero dense candidates, zero lexical candidates, and HTTP 200 with an empty final result.
