# Block 4 Phase 01 — Pre-flight

Status: PASS

The untouched baseline was run in the declared Docker runtime before Block 4 source changes:

```text
python -m pytest tests -v
collected: 43
passed: 43
failed: 0
warnings: 6
duration: 84.33s
```

Inspected contracts and runtime:

- PostgreSQL: 15.19.
- pgvector: 0.5.1.
- `chunk_indexes.embedding`: `vector(768)`.
- `ix_chunk_indexes_embedding`: HNSW with `vector_cosine_ops`, `m=16`, `ef_construction=64`.
- `ix_chunk_indexes_lexical_tsv`: GIN.
- Frozen model: `intfloat/multilingual-e5-base`.
- Frozen index version: `block3-v1`.
- API and indexing worker both mount Docker volume `rag_model_cache` at `/root/.cache/huggingface`.
- Pre-change PostgreSQL table count: 10.

The host Python installation lacked declared project dependencies, so the authoritative baseline was executed in the API image built from `requirements.txt`.
