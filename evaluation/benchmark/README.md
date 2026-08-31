# Isolated Capacity Benchmark

This environment is intentionally separate from normal development. It uses Docker project `rag-benchmark`, independent PostgreSQL, Redis, and MinIO volumes, and only mounts the existing canonical E5 cache read-only.

## Start

1. Copy `.env.benchmark.example` to ignored `.env.benchmark`, set local benchmark-only passwords, and keep `BENCHMARK_E5_CACHE_VOLUME=rag_model_cache` unless the local canonical E5 cache volume has another name.
2. Run `docker compose -p rag-benchmark --env-file .env.benchmark -f deployment/docker-compose.benchmark.yml up -d --build`.
3. Verify targets with `docker compose -p rag-benchmark --env-file .env.benchmark -f deployment/docker-compose.benchmark.yml exec benchmark-api python -m evaluation.benchmark.snapshot`.

The migration and seed services create the independent schema and load the committed `legal_retrieval_v1.json` fixture. The seed refuses non-empty targets and all benchmark tools require the `benchmark` profile, `rag-benchmark-v1` marker, benchmark Postgres/Redis hosts, and `benchmark-documents` bucket.

## Fixture and smoke proof

The fixture contains one real indexed legal document, 18 pages, 115 legal units, 121 chunks, and 121 real 768-D Block 3 embeddings. Its source PDF is the checked-in corpus input whose SHA-256 is verified before upload to the benchmark bucket.

Run `docker compose -p rag-benchmark --env-file .env.benchmark -f deployment/docker-compose.benchmark.yml exec benchmark-api python -m evaluation.benchmark.smoke`. It snapshots before/after the real retrieval path and fails if it detects any mutation. It never calls generation.

## Stop safely

Run `docker compose -p rag-benchmark --env-file .env.benchmark -f deployment/docker-compose.benchmark.yml down`. This stops only benchmark containers and preserves benchmark volumes for reproducibility; it does not affect the normal `rag` project. Do not use `docker compose down -v`.
