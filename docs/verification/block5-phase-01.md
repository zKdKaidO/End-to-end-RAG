# Block 5 Phase 01 — Pre-flight

Status: PASS

The required untouched baseline command completed before Block 5 changes:

```text
docker compose exec -e PYTHONPATH=/app -T api python -m pytest tests -v
collected: 82
passed: 82
failed: 0
skipped: 0
warnings: 6
duration: 85.61s
```

The frozen Block 4 `RetrievedCandidate` schema was inspected directly. Its fields are `chunk_id`, `document_id`, `content_text`, `metadata_json`, `provenance_json`, `dense_score`, `dense_rank`, `lexical_score`, `lexical_rank`, `fusion_score`, and `final_rank`.

Real `sample_legal.pdf` rows confirmed Block 2 metadata keys `document_type`, `document_number`, `issuing_authority`, `issued_date`, and `title`. Real provenance contains `document_id`, `page_start`, and `page_end`. Existing structlog context and request-ID propagation were also inspected.

Pre-change schema state: Alembic `block_3_indexing_models (head)`, 10 PostgreSQL tables.
