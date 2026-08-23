# Retrieval Authorization Boundary V1

For a browser principal, both branch queries include the following indexed predicate before rank/order/limit:

```sql
AND (
  EXISTS (
    SELECT 1 FROM document_access_grants dag
    WHERE dag.document_id = ci.document_id
      AND dag.user_id = :scope_user_id
  )
  OR EXISTS (
    SELECT 1 FROM global_document_access gda
    WHERE gda.document_id = ci.document_id
  )
)
```

The same predicate is present in strict lexical availability, lexeme statistics/fallback, and final lexical candidate selection. Explicit `document_ids` are independently checked before embedding/candidate generation and remain parameterized inside both branches.

No normal product request materializes the authorized corpus as Python UUIDs. There is no corpus-sized `IN` clause and no post-ranking tenant filter. `InternalRetrievalScope` exists only for trusted workers/evaluation code; every browser product route constructs `UserRetrievalScope`.

Hierarchy expansion remains unchanged. Its children belong to the already-authorized anchor document, so authorization is complete before Block 5. Hydration receives only final IDs produced from authorized branch/hierarchy candidates.

Scale evidence is recorded in [verification](../verification/auth-authorization-v1.md): the Dense plan retained the pgvector index scan and the Lexical plan retained the GIN bitmap scan at 10,000 Global + 1,000 private synthetic authorization rows.
