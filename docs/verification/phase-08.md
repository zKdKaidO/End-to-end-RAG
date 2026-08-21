# Phase 8 Verification - Observability, State & Failure Audit

## 1. Files created/modified
- `app/main.py`
- `app/api/routes/documents.py`
- `app/services/upload_service.py`
- `app/queue/rq_client.py`
- `app/worker_main.py`

## 2. What was implemented
- **Structured Logging**: Added `request_id` tracking via FastAPI middleware (`RequestContextMiddleware`).
- **Context Propagation**: Passed `request_id` through API -> UploadService -> Redis (kwargs) -> Worker -> `structlog.contextvars`.
- Log context now includes `request_id`, `job_id`, and `document_id` for both API boundary and Worker boundary.
- **Debug Endpoints**: Implemented GET `/documents/{document_id}/pages` with pagination and text snippeting.
- **Health / Readiness**: Standard `/health` and `/ready` endpoints were already created in Phase 1 and are fully functional.

## 3. Actual Implementation Snippets
Worker Context Binding:
```python
def process_ingestion(job_id: str, document_id: str, request_id: str = None):
    from structlog.contextvars import clear_contextvars, bind_contextvars
    clear_contextvars()
    if request_id:
        bind_contextvars(request_id=request_id)
    bind_contextvars(job_id=job_id, document_id=document_id)
```

**Actual logs captured**:
```json
{"job_id": "cbc4f961-2a62-46c6-9322-fab7c900627c", "document_id": "f8a21c78-e522-41af-a0a7-a01fa893106d", "event": "job_started", "request_id": "5137d1b7-1a40-48fd-8639-5ec4b05b5f7a", "level": "info", "logger": "app.worker_main", "timestamp": "2026-08-17T09:57:12.835180Z"}
{"document_id": "f8a21c78-e522-41af-a0a7-a01fa893106d", "size": 332002, "event": "pdf_downloaded", "job_id": "cbc4f961-2a62-46c6-9322-fab7c900627c", "request_id": "5137d1b7-1a40-48fd-8639-5ec4b05b5f7a", "level": "info", "logger": "app.worker_main", "timestamp": "2026-08-17T09:57:12.881075Z"}
{"job_id": "cbc4f961-2a62-46c6-9322-fab7c900627c", "pages_total": 8, "event": "job_completed", "document_id": "f8a21c78-e522-41af-a0a7-a01fa893106d", "request_id": "5137d1b7-1a40-48fd-8639-5ec4b05b5f7a", "level": "info", "logger": "app.worker_main", "timestamp": "2026-08-17T09:57:13.031552Z"}
```

**Debug APIs Executed**:
- `GET /health` -> `{"status":"ok","service":"api"}` (200 OK)
- `GET /ready` -> `{"status":"ready"}` (200 OK)
- `GET /documents/{document_id}` -> `{"id": "...", "status": "COMPLETED", ...}` (200 OK)
- `GET /ingestion-jobs/{job_id}` -> `{"id": "...", "status": "COMPLETED", "current_stage": "DONE", ...}` (200 OK)
- `GET /documents/{document_id}/pages?limit=10` -> `{"data": [... 8 items ...], "pagination": ...}` (200 OK)

## 4. Failures found
None

## 5. Fixes applied
Added necessary parameter passing to thread `request_id` to async processes.

## 6. Phase Definition of Done
- [x] Structured logs contain trace context (`request_id`, `job_id`, `document_id`)
- [x] Debug endpoints work (`/pages` created)
- [x] `request_id` propagates to worker logs
