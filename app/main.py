import re
import uuid
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import clear_contextvars, bind_contextvars
from app.core.logging import setup_logging, get_logger
from app.api.routes import admin, answer, auth, chat, documents, indexing, retrieval, internal_debug, internal_evaluation
from app.core.config import settings
from app.generation.runtime import close_llm_client
from app.security.middleware import RequestSizeLimitMiddleware, SecurityHeadersMiddleware
from app.deployment.preflight import DeploymentPreflightError, validate_deployment_configuration
from app.deployment.readiness import readiness_report

setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="RAG Data Ingestion API")

allowed_origins = [item.strip() for item in settings.AUTH_TRUSTED_ORIGINS.split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


class TrustedOriginMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
            origin = request.headers.get("origin")
            has_auth_cookie = settings.AUTH_COOKIE_NAME in request.cookies
            if (origin and origin not in allowed_origins) or (has_auth_cookie and not origin):
                return JSONResponse(
                    status_code=403,
                    content={"detail": {"error_code": "UNTRUSTED_ORIGIN", "message": "Request origin is not trusted."}},
                )
        return await call_next(request)

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        clear_contextvars()
        supplied = request.headers.get("X-Request-ID", "")
        request_id = supplied if (
            0 < len(supplied) <= settings.REQUEST_ID_MAX_LENGTH
            and re.fullmatch(r"[A-Za-z0-9._:-]+", supplied)
        ) else str(uuid.uuid4())
        bind_contextvars(request_id=request_id)
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

app.add_middleware(RequestContextMiddleware)
app.add_middleware(TrustedOriginMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(documents.router)
app.include_router(indexing.router)
app.include_router(retrieval.router)
app.include_router(answer.router)
app.include_router(chat.router)
app.include_router(internal_debug.router)
app.include_router(internal_evaluation.router)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up API server...")
    try:
        validate_deployment_configuration()
    except DeploymentPreflightError:
        logger.exception("deployment_preflight_failed")
        raise
    try:
        from app.auth.reconciliation import reconcile_durable_cleanup_intents
        reconcile_durable_cleanup_intents()
    except Exception:
        logger.exception("auth_cleanup_reconciliation_failed")

@app.on_event("shutdown")
async def shutdown_event():
    await close_llm_client()

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "api"}

@app.get("/live")
def liveness_check():
    return {"status": "alive", "service": "api"}

@app.get("/ready")
def readiness_check():
    report = readiness_report()
    return JSONResponse(status_code=200 if report["status"] == "ready" else 503, content=report)
