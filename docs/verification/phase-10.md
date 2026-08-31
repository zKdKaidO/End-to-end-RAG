# Phase 10 Verification - End-to-End Verification Audit

## 1. Clean Canonical E2E Ingestion
**Action**: Ran the historical one-off E2E harness on a clean, truncated database using `tests/fixtures/sample_legal.pdf`. The harness was later removed during repository hygiene after maintained integration tests superseded it.
**HTTP Response**:
- **Status Code**: `202 Accepted`
- **Body**: `{'document': {'id': '16347e1d-b298-42ac-a640-6328967137b3', 'filename': 'sample_legal.pdf', 'status': 'COMPLETED', 'sha256': 'e2847829f8323e9773ced4610a7016a966fac11e13d4ad26bff4606b8b9ee1aa', 'page_count': None, 'created_at': '2026-08-17T09:55:40.417154'}}`
- **Transitions Observed**: `PENDING -> COMPLETED (Stage: DONE)`

## 2. PostgreSQL Direct Verification
- **documents row**: `('16347e1d...', 'sample_legal.pdf', 'e2847829...', 'minio://documents/16347e1d.../original.pdf', None, 'COMPLETED')`
- **ingestion_jobs row**: `('500b6d1c...', '16347e1d...', 'COMPLETED', 'DONE', 8, 8, None, None, None)`
- **document_pages count**: `8`
- **page text previews**:
  - Page 1: `'    CHÍNH PHỦ     CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT N'`
  - Page 4: `'                                 4\n\n      2. Đơn v'`
  - Page 8: `'                                 8\n\n     2. Các Bộ'`

## 3. Page Persistence Idempotency
**Action**: Executed `process_ingestion(job_id, doc_id)` again manually.
**Result**: 
- Re-extracted and updated pages without crashing (`ON CONFLICT DO UPDATE`).
- `document_pages count` remained exactly `8` (no duplicate `(document_id, page_number)` records).

## 4. MinIO State Verification
**Action**: Downloaded object via `boto3` directly.
- **Downloaded object SHA-256**: `e2847829f8323e9773ced4610a7016a966fac11e13d4ad26bff4606b8b9ee1aa`
- **Original sample_legal.pdf SHA-256**: `e2847829f8323e9773ced4610a7016a966fac11e13d4ad26bff4606b8b9ee1aa`
- **documents.sha256**: `e2847829f8323e9773ced4610a7016a966fac11e13d4ad26bff4606b8b9ee1aa`
All matched successfully.

## 5. Deduplication after COMPLETED
**Action**: Re-POSTed the exact same PDF via HTTP after the first ingestion was COMPLETED.
- **HTTP Status**: `202 Accepted`
- **Returned document_id**: Exact match of the existing one.
- **documents count**: 1
- **ingestion_jobs count**: 1
- No new jobs or duplicate processing triggered.

## 6. Restart Persistence
**Action**: `docker compose restart api worker`
**Result**:
- Document still accessible (`GET /documents/{id}`).
- Job still COMPLETED (`GET /ingestion-jobs/{id}`).
- 8 pages still existed in DB.
- Storage survived worker restart.

## 7. Clean Rebuild Check
**Action**: `docker compose down`, `docker compose build`, `docker compose up -d`
**Result**:
- Containers started cleanly.
- `postgres`, `redis`, `minio` healthy.
- `minio-init` exited 0 (bucket already exists).
- `migrate` exited 0 (migrations up to date).
- The E2E document survived and was fully accessible.

**PHASE 10 VERIFICATION: PASS**
