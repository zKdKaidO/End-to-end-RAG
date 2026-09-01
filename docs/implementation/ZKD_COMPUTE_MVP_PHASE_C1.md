# ZKD Compute MVP — Phase C.1

Phase C.1 indexes only local prepared artifacts. It wraps the canonical
`app.indexing.embedder.E5Embedder`, retaining its cache validation, shared
inference lock, `passage: ` input, 768-D float32 normalized embeddings, and
`block3-v1` profile. No alternate model, cloud embedding, retrieval API, or LLM
is used.

`LocalIndexService` adds `chunk_embeddings` (raw 3072-byte float32 BLOBs) and
SQLite FTS5 `chunk_fts` to the local artifact DB. It embeds every prepared
chunk, validates dimensionality, finite unit norm, model identity, one-to-one
coverage, and FTS coverage before atomically committing `index_state=INDEX_READY`.
Failures roll back the SQLite transaction and return the document to
`PREPARED_NOT_INDEXED`; no partial index is advertised.

Indexing is recorded as a durable local `INDEX_DOCUMENT` job. The existing
restart reconciliation prevents stale RUNNING jobs from remaining active.
The only new protocol operation is authenticated `POST /v1/documents/{id}/index`.
Capabilities remain conservative: retrieval and generation are NOT_READY until
P2C.4C.2. No PDF/chunk/vector content leaves local storage or enters logs.

Validation used a real cached canonical E5 model with a synthetic local PDF:
prepare → index → INDEX_READY, with vector and FTS counts matching and vector
blob length 3072 bytes. Browser acceptance remains unavailable and is unrelated
to this local indexing result.

Next: **P2C.4C.2 LOCAL RETRIEVAL + RRF + HIERARCHY**.
