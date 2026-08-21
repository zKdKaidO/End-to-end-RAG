# Debug UI Phase 06 — Document observability

Date: 2026-08-19

- Added a thin read-only aggregate over the existing document, ingestion, processing, indexing, page, legal-unit, chunk, and index records.
- Existing upload endpoint is reused by the frontend; lifecycle code is unchanged.
- Document detail and chunk inspection use stored text, metadata, and provenance only.
- Pipeline errors and current stages are surfaced without stack traces.

Result: PASS.
