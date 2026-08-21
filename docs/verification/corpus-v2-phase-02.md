# Corpus V2 Phase 02 — Manifest and Real Ingestion

Date: 2026-08-19

Result: **PASS**.

All three `READY` PDFs were uploaded through the production `/documents` path and completed the real Block 1 → Block 2 → Block 3 queues. No evaluation-specific ingestion path was created.

| Document key | Document ID | Pages | Legal units | Chunks | `block3-v1` indexes |
|---|---|---:|---:|---:|---:|
| `social_work_practice_2026` | `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` | 18 | 115 | 121 | 121 |
| `people_credit_fund_safety_40_2026` | `78e54e57-fc2e-47b2-919c-c7120776226d` | 21 | 150 | 152 | 152 |
| `civil_servants_consolidated_10_2026` | `ed9f3e56-f3cd-41f6-9ed9-8b70e7f44c25` | 66 | 686 | 692 | 692 |

The frozen processing-to-indexing hook initially created legacy `index_version=v1` rows. The existing canonical `POST /documents/{id}/index` endpoint was then used, without code changes, to create the required `block3-v1` indexes consumed by Block 4. This is recorded as an integration limitation; production behavior was not modified.

Manifest: `evaluation/corpus/legal_corpus_v2_manifest.json`.
