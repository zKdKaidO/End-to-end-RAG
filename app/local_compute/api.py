"""FastAPI loopback protocol server, isolated from the production API."""

from __future__ import annotations

import time
import traceback
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from re import fullmatch
from urllib.parse import unquote

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .documents import LocalDocumentStore
from .errors import LocalComputeError, LocalComputeErrorCode
from .generation import GenerationRoutingRequest, LocalAnswerService
from .grants import PlatformGrantVerifier
from .jobs import LocalJobStore
from .pipeline import LocalDocumentPipelineWorker
from .retrieval import LocalRetrievalStore
from .runtime import LocalComputeRuntime, RuntimeState


ALLOWED_METHODS = "GET, POST, PUT, DELETE, OPTIONS"

ALLOWED_HEADERS = (
    "Content-Type, "
    "X-ZKD-Local-Grant, "
    "X-ZKD-Browser-Nonce, "
    "X-ZKD-Local-Session, "
    "X-ZKD-Timestamp, "
    "X-ZKD-Nonce, "
    "X-ZKD-MAC, "
    "X-ZKD-Protocol-Version, "
    "X-ZKD-Filename"
)

ANSWER_PREFLIGHT_PATH = "/v1/answers"
ANSWER_TRANSPORT_PROBE_PATH = "/v1/transport-probe"
HTTP_HEADER_NAME = r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+"

ROUTE_OPERATIONS = {
    ("GET", "/v1/runtime"): "jobs",
    ("GET", "/v1/capabilities"): "jobs",
    ("POST", "/v1/probe/binary"): "documents",
    ("PUT", "/v1/documents/{document_id}/source"): "documents",
    ("DELETE", "/v1/documents/{document_id}"): "documents",
    ("POST", "/v1/documents/{document_id}/prepare"): "documents",
    ("GET", "/v1/documents"): "documents",
    ("GET", "/v1/documents/{document_id}"): "documents",
    ("GET", "/v1/jobs/{job_id}"): "jobs",
    ("POST", "/v1/jobs/{job_id}:cancel"): "jobs",
    ("POST", "/v1/documents/{document_id}/index"): "documents",
    ("POST", "/v1/queries"): "retrieval",
    ("POST", "/v1/answers"): "answer",
    ("POST", ANSWER_TRANSPORT_PROBE_PATH): "answer",
}


def _safe_exception_location(error: BaseException) -> dict[str, object]:
    """Return a bounded, content-free traceback summary for a failure record.

    Exception messages and full tracebacks can contain request or document
    content. A basename, line number, and function name are sufficient to
    correlate an unexpected error with the frozen application image without
    persisting that data.
    """

    frames = traceback.extract_tb(error.__traceback__)
    if not frames:
        return {}
    safe_frames = [
        {
            # Tracebacks can carry Windows source paths even when a focused
            # regression runs inside the Linux API container. Normalize both
            # separators before retaining the basename only.
            "module": Path(frame.filename.replace("\\", "/")).name,
            "line": frame.lineno,
            "function": frame.name,
        }
        for frame in frames[-8:]
    ]
    frame = safe_frames[-1]
    details: dict[str, object] = {
        "failure_module": frame["module"],
        "failure_line": frame["line"],
        "failure_function": frame["function"],
        "failure_frame_chain": safe_frames,
    }
    # TypeError text may include arbitrary application data. Retain only the
    # fixed CPython weak-reference diagnostic, and only its type token.
    if isinstance(error, TypeError):
        match = fullmatch(
            r"cannot create weak reference to '([A-Za-z_][A-Za-z0-9_.]*)' object",
            str(error),
        )
        if match:
            details["failure_key_type"] = match.group(1)
            details["failure_safe_message"] = (
                "cannot create weak reference to '"
                f"{match.group(1)}' object"
            )
    return details


def _error_response(
    error: LocalComputeError,
    request_id: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "request_id": request_id,
            "error": {
                "code": error.code.value,
                "message": error.message,
            },
        },
    )


def _decode_filename_header(
    value: str,
) -> str:
    if not value:
        return "document.pdf"

    try:
        decoded = unquote(
            value,
            encoding="utf-8",
            errors="strict",
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise LocalComputeError(
            LocalComputeErrorCode.INVALID_REQUEST,
            "Invalid UTF-8 document filename.",
        ) from exc

    if (
        not decoded
        or "\x00" in decoded
        or "\r" in decoded
        or "\n" in decoded
    ):
        raise LocalComputeError(
            LocalComputeErrorCode.INVALID_REQUEST,
            "Invalid document filename.",
        )

    return decoded


class LocalOriginPolicyMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        runtime: LocalComputeRuntime,
    ):
        super().__init__(app)
        self.runtime = runtime

    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        started_at = time.monotonic()

        request_id = (
            request.headers.get("X-Request-ID")
            or str(uuid.uuid4())
        )

        request.state.request_id = request_id

        origin = request.headers.get("origin")

        if (
            request.method == "POST"
            and request.url.path == ANSWER_PREFLIGHT_PATH
        ):
            self._audit_answer_ingress(request, origin)

        if (
            origin
            and origin not in self.runtime.settings.allowed_origins
        ):
            response = _error_response(
                LocalComputeError(
                    LocalComputeErrorCode.ORIGIN_NOT_ALLOWED
                ),
                request_id,
            )

            self._audit(
                request_id,
                request,
                started_at,
                response.status_code,
            )

            return response

        if request.method == "OPTIONS":
            if (
                not origin
                or not request.headers.get(
                    "access-control-request-method"
                )
            ):
                response = _error_response(
                    LocalComputeError(
                        LocalComputeErrorCode.INVALID_REQUEST
                    ),
                    request_id,
                )

                self._audit(
                    request_id,
                    request,
                    started_at,
                    response.status_code,
                )

                return response

            if (
                origin
                not in self.runtime.settings.allowed_origins
            ):
                response = _error_response(
                    LocalComputeError(
                        LocalComputeErrorCode.ORIGIN_NOT_ALLOWED
                    ),
                    request_id,
                )

                self._audit(
                    request_id,
                    request,
                    started_at,
                    response.status_code,
                )

                return response

            headers = _cors_headers(
                origin,
                request.headers.get(
                    "access-control-request-private-network"
                )
                == "true",
            )

            response = JSONResponse(
                status_code=204,
                content=None,
                headers=headers,
            )

            self._audit_answer_preflight(
                request,
                origin,
                headers,
                response.status_code,
            )

            self._audit(
                request_id,
                request,
                started_at,
                response.status_code,
            )

            return response

        response = await call_next(request)

        if (
            origin
            in self.runtime.settings.allowed_origins
        ):
            for key, value in _cors_headers(
                origin,
                False,
            ).items():
                response.headers[key] = value

        response.headers["X-Request-ID"] = request_id

        self._audit(
            request_id,
            request,
            started_at,
            response.status_code,
        )

        return response

    def _audit_answer_preflight(
        self,
        request: Request,
        origin: str,
        response_headers: dict[str, str],
        status_code: int,
    ) -> None:
        """Capture only actual-answer preflight header names for a production diagnosis."""
        if (
            request.url.path != ANSWER_PREFLIGHT_PATH
            or self.runtime.audit_log is None
        ):
            return

        requested_headers = _normalized_requested_header_names(
            request.headers.get("access-control-request-headers")
        )
        self.runtime.audit_log.record_cors_preflight(
            path=request.url.path,
            origin=origin,
            requested_method=request.headers.get(
                "access-control-request-method"
            )
            or "",
            requested_headers=requested_headers,
            private_network_requested=request.headers.get(
                "access-control-request-private-network"
            )
            == "true",
            response_headers=response_headers,
            status_code=status_code,
        )

    def _audit_answer_ingress(
        self,
        request: Request,
        origin: str | None,
    ) -> None:
        """Emit before body reads, authentication, validation, and routing."""
        if self.runtime.audit_log is None:
            return

        content_length = request.headers.get("content-length")
        try:
            parsed_length = int(content_length) if content_length else None
        except ValueError:
            parsed_length = None

        self.runtime.audit_log.record_answer_transport_stage(
            "answers_http_ingress",
            method=request.method,
            path=request.url.path,
            origin=(
                origin
                if origin in self.runtime.settings.allowed_origins
                else "UNTRUSTED_ORIGIN"
            ),
            content_type=_safe_content_type(
                request.headers.get("content-type")
            ),
            content_length=parsed_length,
            request_header_names=sorted(
                {name.lower() for name in request.headers.keys()}
            ),
        )

    def _audit(
        self,
        request_id: str,
        request: Request,
        started_at: float,
        status_code: int,
    ) -> None:
        if self.runtime.audit_log is not None:
            self.runtime.audit_log.record(
                request_id=request_id,
                operation=f"{request.method} {request.url.path}",
                duration_ms=round(
                    (
                        time.monotonic()
                        - started_at
                    )
                    * 1000
                ),
                status_code=status_code,
            )


def _cors_headers(
    origin: str,
    private_network: bool,
) -> dict[str, str]:
    headers = {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": ALLOWED_METHODS,
        "Access-Control-Allow-Headers": ALLOWED_HEADERS,
        "Access-Control-Max-Age": "300",
        "Vary": (
            "Origin, "
            "Access-Control-Request-Method, "
            "Access-Control-Request-Headers, "
            "Access-Control-Request-Private-Network"
        ),
    }

    if private_network:
        headers[
            "Access-Control-Allow-Private-Network"
        ] = "true"

    return headers


def _normalized_requested_header_names(
    value: str | None,
) -> list[str]:
    """Return an ordered, de-duplicated list of valid HTTP header names only."""
    if not value:
        return []

    names: list[str] = []
    for raw_name in value.split(","):
        name = raw_name.strip().lower()
        if name and fullmatch(HTTP_HEADER_NAME, name) and name not in names:
            names.append(name)
    return names


def _safe_content_type(
    value: str | None,
) -> str:
    """Keep diagnostics from retaining an arbitrary header value."""
    media_type = (value or "").split(";", 1)[0].strip().lower()
    if media_type == "application/json":
        return media_type
    if not media_type:
        return "NONE"
    return "OTHER"


def create_local_compute_app(
    runtime: LocalComputeRuntime,
) -> FastAPI:
    pipeline_worker = LocalDocumentPipelineWorker(
        runtime.settings,
        runtime.catalog,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        pipeline_worker.start()

        try:
            yield
        finally:
            pipeline_worker.stop()

    app = FastAPI(
        title="ZKD Compute local control service",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    app.state.pipeline_worker = pipeline_worker

    app.add_middleware(
        LocalOriginPolicyMiddleware,
        runtime=runtime,
    )

    documents = LocalDocumentStore(
        runtime.settings,
        runtime.catalog,
    )

    jobs = LocalJobStore(
        runtime.catalog
    )

    @app.exception_handler(LocalComputeError)
    async def local_compute_error_handler(
        request: Request,
        error: LocalComputeError,
    ):
        return _error_response(
            error,
            getattr(
                request.state,
                "request_id",
                str(uuid.uuid4()),
            ),
        )

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "zkd-compute-control",
            "pipeline_worker": (
                "RUNNING"
                if pipeline_worker.running
                else "STOPPED"
            ),
        }

    @app.post("/v1/sessions")
    async def create_session(
        request: Request,
    ):
        origin = request.headers.get("origin")

        if not origin:
            raise LocalComputeError(
                LocalComputeErrorCode.ORIGIN_NOT_ALLOWED
            )

        if (
            runtime.state
            == RuntimeState.UPDATE_REQUIRED
        ):
            raise LocalComputeError(
                LocalComputeErrorCode.UPDATE_REQUIRED
            )

        if runtime.state == RuntimeState.REVOKED:
            raise LocalComputeError(
                LocalComputeErrorCode.NOT_PAIRED
            )

        grant = request.headers.get(
            "X-ZKD-Local-Grant",
            "",
        )

        browser_nonce = request.headers.get(
            "X-ZKD-Browser-Nonce",
            "",
        )

        if not isinstance(
            runtime.grant_verifier,
            PlatformGrantVerifier,
        ):
            runtime.grant_verifier.verify(
                grant,
                origin,
            )

            session = runtime.sessions.create_session(
                origin
            )
        else:
            verified = runtime.grant_verifier.validate(
                grant,
                origin,
                browser_nonce,
            )

            session = runtime.sessions.create_session(
                origin,
                user_id=verified.user_id,
                device_id=verified.device_id,
                credential_epoch=verified.credential_epoch,
                endpoint_generation=verified.endpoint_generation,
                browser_nonce=verified.browser_nonce,
                allowed_operations=verified.operations,
            )

            runtime.grant_verifier.consume(
                verified
            )

        return {
            "request_id": request.state.request_id,
            "local_session_id": session.session_id,
            "session_key": session.session_key,
            "expires_at": session.expires_at,
            "protocol_version": runtime.settings.protocol_version,
            "endpoint_generation": runtime.endpoint_generation,
            "allowed_operations": sorted(
                session.allowed_operations
            ),
        }

    def operation_for(
        request: Request,
    ) -> str:
        def part_matches(
            template_part: str,
            path_part: str,
        ) -> bool:
            if "{" not in template_part:
                return (
                    template_part
                    == path_part
                )

            prefix, _, remainder = (
                template_part.partition("{")
            )

            _, closing, suffix = (
                remainder.partition("}")
            )

            return (
                bool(closing)
                and path_part.startswith(prefix)
                and path_part.endswith(suffix)
                and len(path_part)
                > (
                    len(prefix)
                    + len(suffix)
                )
            )

        path = request.url.path

        for (
            method,
            route_template,
        ), operation in ROUTE_OPERATIONS.items():
            if method != request.method:
                continue

            template_parts = (
                route_template
                .strip("/")
                .split("/")
            )

            path_parts = (
                path
                .strip("/")
                .split("/")
            )

            if (
                len(template_parts)
                != len(path_parts)
            ):
                continue

            if all(
                part_matches(
                    template_part,
                    path_part,
                )
                for template_part, path_part
                in zip(
                    template_parts,
                    path_parts,
                )
            ):
                return operation

        raise LocalComputeError(
            LocalComputeErrorCode.OPERATION_NOT_ALLOWED
        )

    def record_answer_stage(
        request: Request,
        event_name: str,
        **fields: object,
    ) -> None:
        if (
            request.url.path == ANSWER_PREFLIGHT_PATH
            and request.method == "POST"
            and runtime.audit_log is not None
        ):
            runtime.audit_log.record_answer_transport_stage(
                event_name,
                **fields,
            )

    async def authenticate(
        request: Request,
        *,
        max_bytes: int | None = None,
    ) -> None:
        is_answer = (
            request.method == "POST"
            and request.url.path == ANSWER_PREFLIGHT_PATH
        )

        if is_answer:
            record_answer_stage(request, "answers_auth_begin")

        try:
            origin = request.headers.get("origin")

            if not origin:
                raise LocalComputeError(
                    LocalComputeErrorCode.ORIGIN_NOT_ALLOWED
                )

            if not request.headers.get(
                "X-ZKD-Local-Session"
            ):
                raise LocalComputeError(
                    LocalComputeErrorCode.AUTH_REQUIRED
                )

            if (
                request.headers.get(
                    "X-ZKD-Protocol-Version"
                )
                != runtime.settings.protocol_version
            ):
                runtime.set_update_required()

                raise LocalComputeError(
                    LocalComputeErrorCode.UPDATE_REQUIRED
                )

            body = await request.body()

            if is_answer:
                record_answer_stage(request, "answers_body_received")

            limit = (
                max_bytes
                if max_bytes is not None
                else runtime.settings.request_body_max_bytes
            )

            if len(body) > limit:
                raise LocalComputeError(
                    LocalComputeErrorCode.PAYLOAD_TOO_LARGE
                )

            session = runtime.sessions.validate(
                request.method,
                request.url.path,
                body,
                origin,
                request.headers,
                operation_for(request),
            )

            runtime.validate_session_binding(
                session
            )
        except LocalComputeError as exc:
            if is_answer:
                record_answer_stage(
                    request,
                    f"answers_auth_rejected:{exc.code.value}",
                )
            raise

        if is_answer:
            record_answer_stage(request, "answers_auth_accepted")

    def require_document(
        document_id: str,
    ) -> dict:
        document = documents.get(
            document_id
        )

        if not document:
            raise LocalComputeError(
                LocalComputeErrorCode.DOCUMENT_NOT_FOUND
            )

        return document

    def enqueue_document_pipeline(
        document_id: str,
        *,
        force_reindex: bool = False,
    ) -> dict:
        with runtime.catalog.document_lock(
            document_id
        ):
            document = require_document(
                document_id
            )

            if force_reindex:
                preparation_state = (
                    str(
                        document.get(
                            "preparation_state",
                            "",
                        )
                    )
                    .strip()
                    .upper()
                )

                artifact_id = document.get(
                    "active_artifact_id"
                )

                if (
                    preparation_state
                    == "INDEX_READY"
                ):
                    if not artifact_id:
                        raise LocalComputeError(
                            LocalComputeErrorCode.CAPABILITY_UNAVAILABLE,
                            "Indexed document has no active artifact.",
                        )

                    now = int(time.time())

                    with runtime.catalog._connect() as connection:
                        connection.execute(
                            """
                            UPDATE local_documents
                            SET preparation_state='PREPARED_NOT_INDEXED',
                                last_error_code=NULL,
                                updated_at=?
                            WHERE document_id=?
                            """,
                            (
                                now,
                                document_id,
                            ),
                        )

            job_id = jobs.enqueue_pipeline(
                document_id
            )

            job = jobs.get(
                job_id
            )

        if not job:
            raise LocalComputeError(
                LocalComputeErrorCode.INTERNAL_COMPUTE_ERROR,
                "Durable local pipeline job was not created.",
            )

        return {
            "job_id": job_id,
            "document_id": document_id,
            "state": job["state"],
            "stage": job["stage"],
            "progress": job["progress"],
        }

    @app.get("/v1/runtime")
    async def get_runtime(
        request: Request,
    ):
        await authenticate(request)

        return {
            "request_id": request.state.request_id,
            **runtime.runtime_info(),
        }

    @app.get("/v1/capabilities")
    async def get_capabilities(
        request: Request,
    ):
        await authenticate(request)

        router = runtime.generation_router()

        availability = (
            await router.availability()
        )

        runtime.update_generation_capability(
            availability.state.value
        )

        return {
            "request_id": request.state.request_id,
            "protocol_version": runtime.settings.protocol_version,
            "endpoint_generation": runtime.endpoint_generation,
            "runtime_control_service": (
                "READY"
                if runtime.state
                == RuntimeState.READY
                else runtime.state.value
            ),
            "document_pipeline": (
                "READY"
                if pipeline_worker.running
                else "UNAVAILABLE"
            ),
            "capabilities": runtime.capabilities(),
            "generation_provider": availability.provider_type.value,
            "generation_model_id": availability.model_id,
            "generation_routing": await router.capability_report(),
        }

    @app.post("/v1/probe/binary")
    async def synthetic_binary(
        request: Request,
    ):
        await authenticate(request)

        body = await request.body()

        return {
            "request_id": request.state.request_id,
            "received_bytes": len(body),
            "received_at": int(time.time()),
        }

    @app.post(ANSWER_TRANSPORT_PROBE_PATH)
    async def answer_transport_probe(
        request: Request,
    ):
        """Authenticated, no-persistence diagnostic for browser POST transport.

        It deliberately reuses the existing ``answer`` grant operation, so the
        grant/security contract is unchanged. Only an empty body or one of two
        fixed tiny JSON bodies is accepted.
        """
        await authenticate(request, max_bytes=32)
        body = await request.body()

        if body not in {
            b"",
            b'{"probe":"p2"}',
            b'{"probe":"p3"}',
        }:
            raise LocalComputeError(
                LocalComputeErrorCode.INVALID_REQUEST
            )

        if body and _safe_content_type(
            request.headers.get("content-type")
        ) != "application/json":
            raise LocalComputeError(
                LocalComputeErrorCode.INVALID_REQUEST
            )

        return {
            "request_id": request.state.request_id,
            "status": "ok",
        }

    @app.put(
        "/v1/documents/{document_id}/source"
    )
    async def accept_document(
        document_id: str,
        request: Request,
    ):
        await authenticate(
            request,
            max_bytes=
                runtime.settings.source_pdf_max_bytes,
        )

        body = await request.body()

        encoded_filename = request.headers.get(
            "X-ZKD-Filename",
            "document.pdf",
        )

        filename = _decode_filename_header(
            encoded_filename
        )

        result = documents.accept_document(
            document_id,
            (body,),
            filename,
            request.headers.get(
                "content-type",
                "",
            ),
        )

        return {
            "request_id": request.state.request_id,
            **result,
        }

    @app.post(
        "/v1/documents/{document_id}/prepare"
    )
    async def prepare_document(
        document_id: str,
        request: Request,
    ):
        await authenticate(request)

        result = enqueue_document_pipeline(
            document_id
        )

        return {
            "request_id": request.state.request_id,
            **result,
        }

    @app.get(
        "/v1/documents/{document_id}"
    )
    async def get_document_state(
        document_id: str,
        request: Request,
    ):
        await authenticate(request)

        document = require_document(
            document_id
        )

        safe_document = {
            key: value
            for key, value
            in document.items()
            if key not in {
                "source_relative_path"
            }
        }

        safe_document[
            "latest_job"
        ] = jobs.latest_for_document(
            document_id
        )

        return {
            "request_id": request.state.request_id,
            **safe_document,
        }

    @app.get("/v1/documents")
    async def list_documents(
        request: Request,
    ):
        await authenticate(request)

        local_documents = (
            documents.list_documents()
        )

        result = []

        for document in local_documents:
            safe_document = dict(
                document
            )

            document_id = (
                safe_document.get(
                    "document_id"
                )
            )

            safe_document[
                "latest_job"
            ] = (
                jobs.latest_for_document(
                    document_id
                )
                if document_id
                else None
            )

            result.append(
                safe_document
            )

        return {
            "request_id": request.state.request_id,
            "documents": result,
        }

    @app.delete(
        "/v1/documents/{document_id}"
    )
    async def delete_document(
        document_id: str,
        request: Request,
    ):
        await authenticate(request)

        result = documents.delete_document(
            document_id
        )

        return {
            "request_id": request.state.request_id,
            **result,
        }

    @app.get(
        "/v1/jobs/{job_id}"
    )
    async def get_job_state(
        job_id: str,
        request: Request,
    ):
        await authenticate(request)

        job = jobs.get(
            job_id
        )

        if not job:
            raise LocalComputeError(
                LocalComputeErrorCode.JOB_NOT_FOUND
            )

        return {
            "request_id": request.state.request_id,
            **job,
        }

    @app.post(
        "/v1/jobs/{job_id}:cancel"
    )
    async def cancel_job(
        job_id: str,
        request: Request,
    ):
        await authenticate(request)

        if not jobs.request_cancel(
            job_id
        ):
            existing = jobs.get(
                job_id
            )

            if not existing:
                raise LocalComputeError(
                    LocalComputeErrorCode.JOB_NOT_FOUND
                )

            return {
                "request_id": request.state.request_id,
                "job_id": job_id,
                "state": existing["state"],
            }

        return {
            "request_id": request.state.request_id,
            "job_id": job_id,
            "state": "CANCEL_REQUESTED",
        }

    @app.post(
        "/v1/documents/{document_id}/index"
    )
    async def index_document(
        document_id: str,
        request: Request,
    ):
        await authenticate(request)

        result = enqueue_document_pipeline(
            document_id,
            force_reindex=True,
        )

        return {
            "request_id": request.state.request_id,
            **result,
        }

    @app.post("/v1/queries")
    async def query_document_set(
        request: Request,
    ):
        await authenticate(request)

        try:
            payload = await request.json()
        except ValueError as exc:
            raise LocalComputeError(
                LocalComputeErrorCode.INVALID_REQUEST
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise LocalComputeError(
                LocalComputeErrorCode.INVALID_REQUEST
            )

        retrieval = LocalRetrievalStore(runtime.settings, runtime.catalog)
        retrieval_args = (payload.get("query_text"), payload.get("document_ids"))
        if "answer_mode" in payload:
            retrieval_args += (payload.get("answer_mode"),)
        results, hierarchy = retrieval.query_document_set_with_diagnostics(*retrieval_args)

        return {
            "request_id": request.state.request_id,
            "results": results,
            "hierarchy": hierarchy,
        }

    @app.post("/v1/answers")
    async def answer_document_set(
        request: Request,
    ):
        await authenticate(request)

        record_answer_stage(request, "answers_schema_begin")

        try:
            payload = await request.json()
        except ValueError as exc:
            record_answer_stage(
                request,
                "answers_schema_rejected:INVALID_REQUEST",
            )
            raise LocalComputeError(
                LocalComputeErrorCode.INVALID_REQUEST
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            record_answer_stage(
                request,
                "answers_schema_rejected:INVALID_REQUEST",
            )
            raise LocalComputeError(
                LocalComputeErrorCode.INVALID_REQUEST
            )

        if any(
            key in payload
            for key in (
                "endpoint",
                "credential",
                "api_key",
                "provider_secret",
            )
        ):
            record_answer_stage(
                request,
                "answers_schema_rejected:INVALID_REQUEST",
            )
            raise LocalComputeError(
                LocalComputeErrorCode.INVALID_REQUEST,
                "Provider endpoints and credentials are not accepted by this operation.",
            )

        record_answer_stage(request, "answers_schema_accepted")
        record_answer_stage(request, "answers_handler_begin")

        current_stage = "answers_handler_begin"

        def failure_boundary(stage: str) -> str:
            if stage in {
                "answers_document_resolution_begin",
                "answers_document_resolution_done",
                "answers_retrieval_begin",
                "answers_retrieval_done",
                "answers_context_begin",
                "answers_context_done",
            }:
                return "ANYIO_THREADPOOL"
            return "MAIN_EVENT_LOOP"

        def report_answer_stage(stage: str, boundary: str) -> None:
            nonlocal current_stage
            current_stage = stage
            record_answer_stage(
                request,
                stage,
                boundary=boundary,
            )

        try:
            router = runtime.generation_router()
            answer_service = LocalAnswerService(
                runtime.settings,
                runtime.catalog,
                router,
                profile=router.local_provider.profile,
            )

            answer_kwargs = {
                "request_id": request.state.request_id,
                "query_text": payload.get(
                    "query_text"
                ),
                "document_ids": payload.get(
                    "document_ids"
                ),
            }
            if "answer_mode" in payload:
                answer_kwargs["answer_mode"] = payload.get("answer_mode")

            if any(
                key in payload
                for key in (
                    "routing_policy",
                    "provider_config_id",
                    "allow_user_cloud_fallback",
                    "allow_local_fallback",
                )
            ):
                answer_kwargs[
                    "routing"
                ] = GenerationRoutingRequest.from_values(
                    policy=payload.get(
                        "routing_policy"
                    ),
                    provider_config_id=payload.get(
                        "provider_config_id"
                    ),
                    allow_user_cloud_fallback=payload.get(
                        "allow_user_cloud_fallback",
                        False,
                    ),
                    allow_local_fallback=payload.get(
                        "allow_local_fallback",
                        False,
                    ),
                )

            response = (
                await answer_service.answer(
                    **answer_kwargs,
                    stage_reporter=report_answer_stage,
                )
            )

        except LocalComputeError as exc:
            record_answer_stage(
                request,
                "answers_handler_failed",
                exception_class=type(exc).__name__,
                stage=current_stage,
                error_code=exc.code.value,
                boundary=failure_boundary(current_stage),
            )
            if exc.code in {
                LocalComputeErrorCode.MODEL_UNAVAILABLE,
                LocalComputeErrorCode.GENERATION_UNAVAILABLE,
                LocalComputeErrorCode.GENERATION_TIMEOUT,
            }:
                runtime.update_generation_capability(
                    (
                        "MODEL_UNAVAILABLE"
                        if exc.code
                        == LocalComputeErrorCode.MODEL_UNAVAILABLE
                        else "DEGRADED"
                    )
                )

            raise

        except Exception as exc:
            # Keep unexpected local execution failures inside the HTTP
            # boundary. Exception text may contain local data, so the durable
            # diagnostic is limited to a class name and a fixed stage label.
            record_answer_stage(
                request,
                "answers_handler_failed",
                exception_class=type(exc).__name__,
                stage=current_stage,
                error_code=LocalComputeErrorCode.INTERNAL_COMPUTE_ERROR.value,
                boundary=failure_boundary(current_stage),
                **_safe_exception_location(exc),
            )
            return _error_response(
                LocalComputeError(
                    LocalComputeErrorCode.INTERNAL_COMPUTE_ERROR
                ),
                request.state.request_id,
            )

        runtime.update_generation_capability(
            "READY"
        )

        record_answer_stage(
            request,
            "answers_serialization_begin",
            boundary="MAIN_EVENT_LOOP",
        )
        response_content = {
            "request_id": request.state.request_id,
            **response.as_dict(),
        }
        local_response = JSONResponse(content=response_content)
        record_answer_stage(
            request,
            "answers_serialization_done",
            boundary="MAIN_EVENT_LOOP",
        )
        record_answer_stage(
            request,
            "answers_response_ready",
            boundary="MAIN_EVENT_LOOP",
        )
        return local_response

    return app
