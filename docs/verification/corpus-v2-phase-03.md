# Corpus V2 Phase 03 — Integrity, Scale, Diversity, and Duplicates

Date: 2026-08-19

Result: **PASS**.

- Successfully ingested: 3/3 READY documents.
- Totals: 105 pages, 951 legal units, 965 chunks, 965 `block3-v1` indexes.
- Every document has pages, one reconstruction, legal units, chunks, complete provenance, lexical tsvectors, and 768-dimensional multilingual-E5 indexes.
- Average chunks/document: 321.67; minimum: 121; maximum: 692.
- PostgreSQL public tables: 10; database size at audit: 41,500,007 bytes.
- Schema drift: none.

Diversity is real but bounded: social-work practice, people-credit-fund safety, and civil-service management. Same article numbers, repeated legal boilerplate, shared effective-date language, and strong document-size skew support disambiguation, near-duplicate, deeper-rank, and multi-evidence stress cases.

Duplicate observations:

- Duplicate supplied PDFs: 0.
- Exact duplicate chunk groups: 4.
- Diagnostic cross-document embedding-near pairs at cosine similarity ≥0.92: 25. These are not treated as legal equivalence.

Evidence: `evaluation/reports/legal_corpus_v2_integrity.json` and `.md`.
