# Phase 2 — pgvector Enablement

## Files Inspected
- `docker-compose.yml`

## Files Created/Modified
- `postgres/Dockerfile`
- `docker-compose.yml`

## What was implemented
- Created a custom Dockerfile based exactly on `postgres:15-alpine` to compile and install pgvector from source.
- Bypassed LLVM using `make with_llvm=no` to avoid Alpine/LLVM incompatibilities.
- Enabled the extension in PostgreSQL via `CREATE EXTENSION vector;`.

## Commands executed
- `docker compose up -d --build postgres`
- `docker compose exec postgres psql -U postgres -d rag_db -c "CREATE EXTENSION vector; SELECT extversion FROM pg_extension WHERE extname = 'vector';"`
- `docker compose exec postgres psql -U postgres -d rag_db -c "SELECT COUNT(*) FROM documents; SELECT COUNT(*) FROM chunks;"`

## Actual outputs
- Successfully compiled `pgvector` inside `postgres:15-alpine`.
- `extversion` is `0.5.1`.
- Row counts were fully preserved. 

## Failures found
- `make` failed initially because `clang21` wasn't available in Alpine 3.24.
- `make install` failed because LLVM paths were hardcoded to `llvm21` in PostgreSQL PGXS.

## Fixes applied
- Disabled LLVM via `with_llvm=no` during `make`.

## Definition of Done
- pgvector enabled
- Data preserved
- No DB recreation required
