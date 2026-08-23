# Legal-RAG-V3 Implementation Verification

Date: 2026-08-22

## Result

**PASS — implemented as a server-owned runtime option; not activated.**

- Added `app/prompts/legal-rag-v3.txt` using the approved canonical bytes.
- Extended the existing prompt/profile allowlists to address `legal-rag-v3`.
- Kept `GENERATION_PROMPT_VERSION` default at `legal-rag-v2`; `.env` does not override it.
- Added no request field, query parameter, UI control, database object, provider, model, classifier, reranker, judge, or second call.
- V2 and V3 `GenerationProfile` values differ only in `prompt_version`.
- Block 5 continues to supply P0. The V3 prompt contains none of `candidate_origin`, `HIERARCHY_CHILD`, `DIRECT_CHILD`, `anchor_chunk_id`, `anchor_legal_unit_id`, or `hierarchy_anchor_references`.

## Preflight

- Backend: 235 collected, 235 passed, 0 failed, 8 warnings, 90.44s.
- Frontend: 5 files, 11 tests passed, 0 failed, 1.07s.
- Production build: PASS, 30 modules, 130ms.

## Final regression

- Backend: 245 collected, 245 passed, 0 failed, 8 warnings, 92.77s.
- Frontend: 5 files, 11 tests passed, 0 failed, 1.60s.
- Production build: PASS, 30 modules, 174ms.

The ten added backend cases cover prompt hashes/identity, version isolation, unknown-version failure, request override rejection, prompt contract/anti-leakage/P0 independence, real tokenizer delta/budget guard, and SSE reporting of controlled V3 selection. Existing answerability, citation, injection-boundary, stream-error, and disconnect tests remain unchanged and green.

## Architecture audit

Tracked diffs under `app/ingestion`, `app/processing`, `app/indexing`, `app/retrieval`, `app/context`, and `app/db/migrations`: zero. Public tables remain 10; Alembic version remains `block_3_indexing_models`; pgvector remains 0.5.1. No schema migration or reindex was run.

Production final state: `legal-rag-v2`.
