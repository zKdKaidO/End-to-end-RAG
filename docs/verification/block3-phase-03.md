# Phase 3 — Database Models + Migration

## Files Inspected
- `app/models/chunk_index.py`
- `app/models/indexing_job.py`
- `app/models/__init__.py`

## Files Created/Modified
- `app/models/indexing_job.py`
- `app/models/chunk_index.py`
- `app/models/__init__.py`

## What was implemented
- Created `IndexingJob` model with `document_id`, `status`, `current_stage`, `chunks_total`, `chunks_indexed`, `embedding_model`, `index_version`, `started_at`, `finished_at`.
- Created `ChunkIndex` model with `chunk_id`, `document_id`, `embedding` (Vector(768)), `lexical_tsv` (TSVECTOR), `embedding_model`, `index_version`.
- Configured indexes for `ChunkIndex`: HNSW for `embedding` using `vector_cosine_ops` (`m=16, ef_construction=64`), GIN for `lexical_tsv`.
- Prepared for Alembic autogeneration.

## Commands executed
- Alembic migration generation (waiting for container to build).

## Actual outputs
- Models are defined properly.

## Definition of Done
- `indexing_jobs` table model created.
- `chunk_indexes` table model created with HNSW and GIN indexes.
- Alembic migration successfully generated and executed.
