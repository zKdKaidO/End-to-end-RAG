# Isolated Capacity Benchmark

This environment is intentionally separate from normal development. It uses Docker project `rag-benchmark`, independent PostgreSQL, Redis, and MinIO volumes, and only mounts the existing canonical E5 cache read-only.

## Start

1. Copy `.env.benchmark.example` to ignored `.env.benchmark`, set local benchmark-only passwords, and keep `BENCHMARK_E5_CACHE_VOLUME=rag_model_cache` unless the local canonical E5 cache volume has another name.
2. Run `docker compose -p rag-benchmark --env-file .env.benchmark -f deployment/docker-compose.benchmark.yml up -d --build`.
3. Verify targets with `docker compose -p rag-benchmark --env-file .env.benchmark -f deployment/docker-compose.benchmark.yml exec benchmark-api python -m evaluation.benchmark.snapshot`.

The migration and seed services create the independent schema and load the committed `legal_retrieval_v2.json` fixture. The seed refuses a non-empty target unless its deterministic snapshot exactly matches that fixture. All benchmark tools require the `benchmark` profile, `rag-benchmark-v1` marker, benchmark Postgres/Redis hosts, and `benchmark-documents` bucket.

## Fixture and smoke proof

The fixture is a frozen read-only copy of the representative development corpus state: 44 documents, 613 chunks, 613 real normalized 768-D Block 3 embeddings, legal hierarchy/page metadata, and 18 source objects. Object bytes and SHA-256 values are committed under `fixtures/objects`, so future benchmark startup has no runtime dependency on mutable development storage and does not re-embed canonical data.

The optional benchmark worker profile contains only the processing and indexing workers. The generic lifecycle worker is deliberately excluded: its deletion queues would make a read-only capacity benchmark mutable.

Run `docker compose -p rag-benchmark --env-file .env.benchmark -f deployment/docker-compose.benchmark.yml exec benchmark-api python -m evaluation.benchmark.smoke`. It snapshots before/after the real retrieval path and fails if it detects any mutation. It never calls generation.

## Stop safely

Run `docker compose -p rag-benchmark --env-file .env.benchmark -f deployment/docker-compose.benchmark.yml down`. This stops only benchmark containers and preserves benchmark volumes for reproducibility; it does not affect the normal `rag` project. Do not use `docker compose down -v`.
