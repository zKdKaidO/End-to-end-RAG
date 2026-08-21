# Phase 5 — Lexical Engine Integration

## Files Inspected
- `app/repositories/chunk_index_repo.py`
- `app/indexing_worker_main.py`
- `tests/integration/test_chunk_index_repo.py`

## Files Created/Modified
- `app/repositories/chunk_index_repo.py`
- `app/indexing_worker_main.py`
- `tests/integration/test_chunk_index_repo.py`

## What was implemented
- Used PostgreSQL's native `func.to_tsvector('simple', text)` inside the SQLAlchemy `upsert_indexes` routine to safely and efficiently generate lexical tokens entirely within the DB.
- Confirmed Elasticsearch is strictly avoided.
- Index uses the standard GIN index defined in Phase 3.

## Commands executed
- Created `test_upsert_lexical_tsv` to test the TSVECTOR behavior end-to-end.

## Actual outputs
- PostgreSQL TSVECTOR generation properly filters and stems simple keywords.

## Definition of Done
- `to_tsvector` implemented natively in upsert payloads.
- No ES added.
- Upsert logic safely handles conflicts via `on_conflict_do_update` using `index_elements=['chunk_id']`.
