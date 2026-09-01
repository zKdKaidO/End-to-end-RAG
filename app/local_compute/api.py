"""FastAPI loopback protocol server, isolated from the production API."""

from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .errors import LocalComputeError, LocalComputeErrorCode
from .runtime import LocalComputeRuntime, RuntimeState
from .documents import LocalDocumentStore
from .preparation import LocalPreparationService
from .jobs import LocalJobStore
from .indexing import LocalIndexService
from .retrieval import LocalRetrievalStore


ALLOWED_METHODS = "GET, POST, PUT, DELETE, OPTIONS"
ALLOWED_HEADERS = "Content-Type, X-ZKD-Local-Grant, X-ZKD-Local-Session, X-ZKD-Timestamp, X-ZKD-Nonce, X-ZKD-MAC, X-ZKD-Protocol-Version"


def _error_response(error: LocalComputeError, request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"request_id": request_id, "error": {"code": error.code.value, "message": error.message}},
    )


class LocalOriginPolicyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, runtime: LocalComputeRuntime):
        super().__init__(app)
        self.runtime = runtime

    async def dispatch(self, request: Request, call_next):
        started_at = time.monotonic()
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        origin = request.headers.get("origin")
        if origin and origin not in self.runtime.settings.allowed_origins:
            response = _error_response(LocalComputeError(LocalComputeErrorCode.ORIGIN_NOT_ALLOWED), request_id)
            self._audit(request_id, request, started_at, response.status_code)
            return response
        if request.method == "OPTIONS":
            if not origin or not request.headers.get("access-control-request-method"):
                response = _error_response(LocalComputeError(LocalComputeErrorCode.INVALID_REQUEST), request_id)
                self._audit(request_id, request, started_at, response.status_code)
                return response
            if origin not in self.runtime.settings.allowed_origins:
                response = _error_response(LocalComputeError(LocalComputeErrorCode.ORIGIN_NOT_ALLOWED), request_id)
                self._audit(request_id, request, started_at, response.status_code)
                return response
            headers = _cors_headers(origin, request.headers.get("access-control-request-private-network") == "true")
            response = JSONResponse(status_code=204, content=None, headers=headers)
            self._audit(request_id, request, started_at, response.status_code)
            return response
        response = await call_next(request)
        if origin in self.runtime.settings.allowed_origins:
            for key, value in _cors_headers(origin, False).items():
                response.headers[key] = value
        response.headers["X-Request-ID"] = request_id
        self._audit(request_id, request, started_at, response.status_code)
        return response

    def _audit(self, request_id: str, request: Request, started_at: float, status_code: int) -> None:
        if self.runtime.audit_log is not None:
            self.runtime.audit_log.record(
                request_id=request_id,
                operation=f"{request.method} {request.url.path}",
                duration_ms=round((time.monotonic() - started_at) * 1000),
                status_code=status_code,
            )


def _cors_headers(origin: str, private_network: bool) -> dict[str, str]:
    headers = {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": ALLOWED_METHODS,
        "Access-Control-Allow-Headers": ALLOWED_HEADERS,
        "Access-Control-Max-Age": "300",
        "Vary": "Origin, Access-Control-Request-Method, Access-Control-Request-Headers, Access-Control-Request-Private-Network",
    }
    if private_network:
        headers["Access-Control-Allow-Private-Network"] = "true"
    return headers


def create_local_compute_app(runtime: LocalComputeRuntime) -> FastAPI:
    app = FastAPI(title="ZKD Compute local control service", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(LocalOriginPolicyMiddleware, runtime=runtime)

    @app.exception_handler(LocalComputeError)
    async def local_compute_error_handler(request: Request, error: LocalComputeError):
        return _error_response(error, getattr(request.state, "request_id", str(uuid.uuid4())))

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "zkd-compute-control"}

    @app.post("/v1/sessions")
    async def create_session(request: Request):
        origin = request.headers.get("origin")
        if not origin:
            raise LocalComputeError(LocalComputeErrorCode.ORIGIN_NOT_ALLOWED)
        grant = request.headers.get("X-ZKD-Local-Grant", "")
        runtime.grant_verifier.verify(grant, origin)
        session = runtime.sessions.create_session(origin)
        return {
            "request_id": request.state.request_id,
            "local_session_id": session.session_id,
            "session_key": session.session_key,
            "expires_at": session.expires_at,
            "protocol_version": runtime.settings.protocol_version,
            "endpoint_generation": runtime.endpoint_generation,
        }

    async def authenticate(request: Request) -> None:
        origin = request.headers.get("origin")
        if not origin:
            raise LocalComputeError(LocalComputeErrorCode.ORIGIN_NOT_ALLOWED)
        if not request.headers.get("X-ZKD-Local-Session"):
            raise LocalComputeError(LocalComputeErrorCode.AUTH_REQUIRED)
        if request.headers.get("X-ZKD-Protocol-Version") != runtime.settings.protocol_version:
            runtime.set_update_required()
            raise LocalComputeError(LocalComputeErrorCode.UPDATE_REQUIRED)
        body = await request.body()
        if len(body) > runtime.settings.request_body_max_bytes:
            raise LocalComputeError(LocalComputeErrorCode.PAYLOAD_TOO_LARGE)
        runtime.sessions.validate(request.method, request.url.path, body, origin, request.headers)

    @app.get("/v1/runtime")
    async def get_runtime(request: Request):
        await authenticate(request)
        return {"request_id": request.state.request_id, **runtime.runtime_info()}

    @app.get("/v1/capabilities")
    async def get_capabilities(request: Request):
        await authenticate(request)
        return {
            "request_id": request.state.request_id,
            "protocol_version": runtime.settings.protocol_version,
            "endpoint_generation": runtime.endpoint_generation,
            "runtime_control_service": "READY" if runtime.state == RuntimeState.READY else runtime.state.value,
            "capabilities": runtime.capabilities(),
        }

    @app.post("/v1/probe/binary")
    async def synthetic_binary(request: Request):
        await authenticate(request)
        body = await request.body()
        if len(body) > runtime.settings.request_body_max_bytes:
            raise LocalComputeError(LocalComputeErrorCode.PAYLOAD_TOO_LARGE)
        return {"request_id": request.state.request_id, "received_bytes": len(body), "received_at": int(time.time())}

    @app.put("/v1/documents/{document_id}/source")
    async def accept_document(document_id: str, request: Request):
        await authenticate(request)
        body = await request.body()
        filename = request.headers.get("X-ZKD-Filename", "document.pdf")
        result = LocalDocumentStore(runtime.settings, runtime.catalog).accept_document(document_id, (body,), filename, request.headers.get("content-type", ""))
        return {"request_id": request.state.request_id, **result}

    @app.post("/v1/documents/{document_id}/prepare")
    async def prepare_document(document_id: str, request: Request):
        await authenticate(request)
        result = LocalPreparationService(runtime.settings, runtime.catalog).prepare(document_id)
        return {"request_id": request.state.request_id, **result}

    @app.get("/v1/documents/{document_id}")
    async def get_document_state(document_id: str, request: Request):
        await authenticate(request)
        document = LocalDocumentStore(runtime.settings, runtime.catalog).get(document_id)
        if not document: raise LocalComputeError(LocalComputeErrorCode.DOCUMENT_NOT_FOUND)
        return {"request_id": request.state.request_id, **{key: value for key, value in document.items() if key not in {"source_relative_path"}}}

    @app.get("/v1/jobs/{job_id}")
    async def get_job_state(job_id: str, request: Request):
        await authenticate(request)
        job = LocalJobStore(runtime.catalog).get(job_id)
        if not job: raise LocalComputeError(LocalComputeErrorCode.JOB_NOT_FOUND)
        return {"request_id": request.state.request_id, **job}

    @app.post("/v1/jobs/{job_id}:cancel")
    async def cancel_job(job_id: str, request: Request):
        await authenticate(request)
        if not LocalJobStore(runtime.catalog).request_cancel(job_id): raise LocalComputeError(LocalComputeErrorCode.JOB_NOT_FOUND)
        return {"request_id": request.state.request_id, "job_id": job_id, "state": "CANCEL_REQUESTED"}

    @app.post("/v1/documents/{document_id}/index")
    async def index_document(document_id: str, request: Request):
        await authenticate(request)
        return {"request_id": request.state.request_id, **LocalIndexService(runtime.settings, runtime.catalog).index_document(document_id)}

    @app.post("/v1/queries")
    async def query_document_set(request: Request):
        await authenticate(request)
        payload=await request.json()
        return {"request_id":request.state.request_id,"results":LocalRetrievalStore(runtime.settings,runtime.catalog).query_document_set(payload.get("query_text"),payload.get("document_ids"))}


    return app
