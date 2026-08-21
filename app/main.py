import uuid
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import clear_contextvars, bind_contextvars
from app.core.logging import setup_logging, get_logger
from app.api.routes import answer, documents, indexing, retrieval, internal_debug, internal_evaluation
from app.core.config import settings
from app.generation.runtime import close_llm_client

setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="RAG Data Ingestion API")

if settings.DEBUG_UI_ENABLED:
    allowed_origins = [item.strip() for item in settings.DEBUG_UI_ORIGINS.split(",") if item.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        clear_contextvars()
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        bind_contextvars(request_id=request_id)
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

app.add_middleware(RequestContextMiddleware)
app.include_router(documents.router)
app.include_router(indexing.router)
app.include_router(retrieval.router)
app.include_router(answer.router)
app.include_router(internal_debug.router)
app.include_router(internal_evaluation.router)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up API server...")

@app.on_event("shutdown")
async def shutdown_event():
    await close_llm_client()

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "api"}

@app.get("/ready")
def readiness_check():
    # In a real scenario, this would test DB, Redis, and MinIO connections.
    return {"status": "ready"}
