# Block 4 Phase 03 — Dense retrieval

Status: PASS

Dense SQL reads `chunk_indexes`, filters frozen `embedding_model`, dimension, and `index_version`, and orders directly by:

```sql
ORDER BY ci.embedding <=> CAST(:query_vector AS vector) ASC
LIMIT :top_k
```

The distance expression is preserved without a secondary SQL sort. A query-plan eligibility check with sequential scans disabled produced:

```text
Index Scan using ix_chunk_indexes_embedding on chunk_indexes
Order By: (embedding <=> $0)
```

Tests verify shape, score, one-based ranks, Top-K propagation, frozen model/index filters, SQL document pre-filtering, and exclusion of wrong documents. A live dense smoke query against `sample_legal.pdf` returned ordered candidates.

`SET hnsw.iterative_scan` is not present and pgvector was not upgraded. With pgvector 0.5.1, filtered ANN recall can be affected because iterative scanning is unavailable.
