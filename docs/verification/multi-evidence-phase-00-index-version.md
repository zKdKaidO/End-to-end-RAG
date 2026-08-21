# Multi-Evidence Phase 00 — Block 2 → Block 3 Index-Version Audit

Date: 2026-08-19

## Classification

**GENUINE FROZEN-CONTRACT INTEGRATION DEFECT**

The Block 2 processing completion hook in `app/processing_worker_main.py` calls `IndexingJobRepository.create_job(..., index_version="v1", ...)`. The canonical `POST /documents/{document_id}/index` route explicitly uses `block3-v1`, and the frozen Block 4 dense and lexical SQL filters also require `block3-v1`.

The indexing worker does not choose or normalize the version. It persists the exact value stored on the `indexing_jobs` row into `chunk_indexes`. The migration permits arbitrary non-null strings in `chunk_indexes.index_version` and a nullable string in `indexing_jobs.index_version`; it does not establish a canonical default.

## Database evidence

The three Corpus V2 documents each have an earlier automatically created, completed `v1` job followed by the explicitly requested, completed `block3-v1` job. The canonical jobs indexed 121, 152, and 692 chunks respectively. Current `chunk_indexes` contains 1,042 `block3-v1` rows and 1,756 legacy `v1` rows across the development database; Block 4 ignores the latter.

## Minimal correction

Future approved correction: replace the processing hook's hardcoded `v1` with the same shared canonical constant used by the official indexing path and retrieval contract (`block3-v1`), then add an integration test asserting that automatic Block 2 completion enqueues a `block3-v1` job. No migration, reindex redesign, model change, or retrieval change is required.

## Experiment decision

Correction implemented: **NO**.

It is not required to produce valid experiment data because all Corpus V2 chunks already have validated canonical `block3-v1` indexes. All experiment queries explicitly filter `embedding_model=intfloat/multilingual-e5-base`, dimension 768, and `index_version=block3-v1`.
