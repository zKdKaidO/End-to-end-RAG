# ZKD Compute MVP — Phase B

**Scope:** local document acceptance and preparation only.

## Local source and identity

`LocalDocumentStore` accepts byte chunks, not filesystem paths. It enforces the
local size limit, writes an fsynced temporary source, reuses Block 1
`validate_and_hash_pdf`, verifies SHA-256 after same-volume promotion to
`documents/<document_id>/source.pdf`, and persists the immutable source record
in the local catalog. Same ID/same bytes is idempotent; same ID/different bytes
is `DOCUMENT_CONFLICT`; different IDs retain separate source ownership.

## Preparation

`LocalPreparationService` creates a new immutable candidate under
`artifacts/<document_id>/<artifact_id>.staging/`. It wraps existing pure
production components: `PDFExtractor`, `PageCleaner`, `HeaderFooterRemover`,
`DocumentReconstructor`, `MetadataExtractor`, `LegalParser`, and token-safe
`Chunker`. The cached canonical multilingual-E5 tokenizer validates the frozen
512-token `passage: ` contract without loading model weights or embedding.
Textless/scanned PDFs fail as `UNSUPPORTED_TEXTLESS_PDF`; OCR is not added.

The artifact SQLite schema v1 stores metadata/profile, pages, reconstruction
and offset map, hierarchy/legal units, chunks, provenance, and exact token
counts. It stores no embeddings or vector columns. Profile ID is
`zkd-local-artifact-v1`; its fingerprint records parser/chunking, E5 identity,
768-D normalized future embedding requirements, prefix semantics, `block3-v1`,
and local retrieval/hierarchy expectations.

After schema/profile/source/hash/count validation, the candidate directory is
atomically renamed and a catalog transaction selects it. Success is
`PREPARED_NOT_INDEXED`, explicitly not queryable. Failed candidates are removed;
the source and any previous active artifact remain intact. Startup reconciles
stale RUNNING/CANCEL_REQUESTED jobs to `FAILED_INTERRUPTED` and never promotes
staging content.

## Local protocol and privacy

Authenticated loopback routes now include source acceptance, preparation,
document state, job state, and cancellation. They retain P2C.4A origin/session/
MAC policy. No cloud call, manifest sync, PostgreSQL, Redis/RQ, MinIO, E5 model
execution, retrieval, or LLM call occurs. Logs contain only operational IDs and
counts; PDF/page/chunk content is never logged.

## Evidence

`tests/unit/local_compute`: 13 passed. The isolated preparation test creates a
safe synthetic text-native PDF, verifies source SHA/idempotency/conflict,
token-safe chunks and provenance in the artifact SQLite DB, atomic active
promotion, and restart persistence. Invalid and text-empty PDFs fail safely.

The P2C.4A browser gate remains `BROWSER_ACCEPTANCE_NOT_EXECUTABLE`; HTTP tests
are not presented as Chrome/Edge acceptance.

## Next phase

**P2C.4C LOCAL E5 INDEXING + RETRIEVAL** may add local E5 embedding and the
SQLite/FTS5/exact-cosine retrieval adapter behind parity tests.
