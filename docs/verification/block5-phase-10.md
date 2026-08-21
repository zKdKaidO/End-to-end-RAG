# Block 5 Phase 10 — Provenance integrity

Status: PASS

Tests compare each selected evidence directly with its originating frozen Block 4 candidate and verify unchanged:

- `chunk_id`;
- `document_id`;
- `content_text`;
- `metadata_json`;
- `provenance_json`;
- retrieval final rank;
- dense/lexical ranks and diagnostic scores;
- fusion score.

Source IDs are assigned independently and map back through `selected_evidence`; provenance is never reconstructed from prompt text. Page values remain only in original machine-facing provenance and are never invented.
