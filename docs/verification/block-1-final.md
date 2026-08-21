# BLOCK 1 FINAL STATUS: COMPLETE

## Architecture implemented
```text
Client (curl / requests via E2E)
→ FastAPI (Upload API w/ validation, deduplication)
→ PostgreSQL (documents, ingestion_jobs, document_pages tracking)
→ MinIO (Object Storage for original PDFs)
→ Redis/RQ (Message Queue for Async Ingestion)
→ Worker (RQ Consumer with bounded Retry semantics)
→ PyMuPDF (PDFExtractor yielding pages in natural reading order)
→ PostgreSQL document_pages (Batch Upsert Idempotency)
```

## Actual stack versions
- FastAPI: `0.141.1`
- PostgreSQL: `15-alpine`
- MinIO: `7.2.20` (minio-py)
- Redis: `7-alpine` / `redis-py 8.1.0`
- RQ: `2.11.0`
- PyMuPDF: `1.28.2`
- SQLAlchemy: `2.0.52`

## Full file structure
```text
A:\RAG\
├── docker-compose.yml
├── requirements.txt
├── app/
│   ├── main.py
│   ├── worker_main.py
│   ├── api/
│   │   ├── routes/
│   │   │   └── documents.py
│   │   └── dependencies.py
│   ├── core/
│   │   ├── config.py
│   │   ├── exceptions.py
│   │   └── logging.py
│   ├── db/
│   │   └── database.py
│   ├── models/
│   │   ├── document.py
│   │   ├── document_page.py
│   │   └── ingestion_job.py
│   ├── pdf/
│   │   ├── extractor.py
│   │   └── validator.py
│   ├── queue/
│   │   └── rq_client.py
│   ├── repositories/
│   │   ├── document_repo.py
│   │   ├── job_repo.py
│   │   └── page_repo.py
│   ├── schemas/
│   │   └── document.py
│   ├── services/
│   │   └── upload_service.py
│   └── storage/
│       └── minio_client.py
├── tests/
│   ├── integration/
│   ├── unit/
│   └── fixtures/
│       └── sample_legal.pdf
└── docs/
    └── verification/
```

## Database schema
- `documents`: Stores file metadata (filename, size, sha256 `UNIQUE`, storage_uri, status).
- `ingestion_jobs`: Links to documents, tracks `status`, `current_stage`, `error_*`, `pages_processed/total`.
- `document_pages`: Stores extracted text with `UNIQUE(document_id, page_number)`.

## State machine
1. **API**: `UPLOADING` -> `PENDING` (on enqueue success) OR `FAILED` (on any infra error).
2. **Worker**: `PROCESSING` (Stage: `DOWNLOAD` -> `TEXT_EXTRACTION`).
3. **Completion**: `COMPLETED` (Stage: `DONE`).
4. **Error**: Uses RQ bound retries. Transient exception yields retry, final exception yields `FAILED` and error metadata.

## Test summary
- **Unit**: 1 (PyMuPDF exact parsing and layout)
- **Integration**: 15 (Upload flow, Dedup, Queue/Storage failure mapping, Regressions, Worker success/failure paths, MinIO adapters)
- **End-to-End**: 1 (Full upload through HTTP to Worker processing and final page text preview via Debug Endpoint).
- Total `pytest -v` tests passed: 16 (14.50s).

## Canonical fixture
- **filename**: sample_legal.pdf
- **SHA-256**: e2847829f8323e9773ced4610a7016a966fac11e13d4ad26bff4606b8b9ee1aa
- **page_count**: 8

## End-to-end proof
- **document_id**: f802f4c1-58e5-4f09-aaf8-f8962c19b09e
- **job_id**: f31b514b-22b0-4ec3-ba00-0e1db4e815bc (varies slightly by run)
- **MinIO object key**: documents/f802f4c1-58e5-4f09-aaf8-f8962c19b09e/original.pdf
- **page count**: 8
- **final status**: COMPLETED

## Known limitations
1. **10 MB upload limit**: Configured via environment variable. File bytes are loaded in memory for streaming which handles 10MB fine, but limits handling large 500MB documents.
2. **Text-native PDFs only**: Relies on PyMuPDF text layer; no OCR engine included yet for scanned pages.
3. **Single-user assumption**: Deduplication strictly ignores multi-tenant separation. If file X is uploaded by anyone, it returns the same document.

**BLOCK 1 DATA INGESTION COMPLETE**
