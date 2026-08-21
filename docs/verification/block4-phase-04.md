# Block 4 Phase 04 — Lexical retrieval

Status: PASS

Lexical SQL uses:

```sql
websearch_to_tsquery('simple', :query_text)
ci.lexical_tsv @@ lexical_query.value
ts_rank_cd(ci.lexical_tsv, lexical_query.value)
```

Tests verify one-based ranking, Top-K propagation, SQL document pre-filtering, wrong-document exclusion, and an empty result for an unmatched token.

Live keyword smoke query `bảo hiểm hưu trí bổ sung người lao động` returned these ranked chunk IDs:

1. `6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1`
2. `e3e6bd37-81aa-470c-bbc1-4e596ce51b81`
3. `5a5aeeb5-ce90-41de-837c-332bd208f897`
