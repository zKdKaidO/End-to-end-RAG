import uuid

import pytest
from redis import Redis
from sqlalchemy import delete, text

from app.auth.dependencies import get_current_principal
from app.auth.principal import Principal
from app.main import app
from app.core.config import settings
from app.db.database import SessionLocal
from app.models.auth import DocumentAccessGrant, GlobalDocumentAccess
from app.models.compute_control import LocalDocumentManifest
from app.models.document import Document
from app.storage.minio_client import minio_client


LEGACY_TEST_PRINCIPAL = Principal(
    user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    role="ADMIN",
    auth_session_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
)


@pytest.fixture(autouse=True)
def authenticated_frozen_baseline(request):
    """Existing frozen route tests execute as the migrated legacy admin.

    Auth-specific tests opt into real cookie/session resolution with ``real_auth``.
    This is a pytest-only dependency override and cannot affect a deployed app.
    """
    if request.node.get_closest_marker("real_auth"):
        yield
        return
    previous = app.dependency_overrides.get(get_current_principal)
    app.dependency_overrides[get_current_principal] = lambda: LEGACY_TEST_PRINCIPAL
    yield
    if previous is None:
        app.dependency_overrides.pop(get_current_principal, None)
    else:
        app.dependency_overrides[get_current_principal] = previous


@pytest.fixture(autouse=True)
def clear_distributed_security_test_state():
    """Keep rate/admission state isolated without weakening production code."""
    redis = Redis.from_url(settings.REDIS_URL)
    for pattern in (b"security:v1:login:*", b"security:v1:generation:*"):
        keys = list(redis.scan_iter(match=pattern))
        if keys:
            redis.delete(*keys)
    yield
    for pattern in (b"security:v1:login:*", b"security:v1:generation:*"):
        keys = list(redis.scan_iter(match=pattern))
        if keys:
            redis.delete(*keys)


@pytest.fixture(autouse=True)
def isolated_document_corpus(request):
    """Clean only resources created by explicitly marked legacy integration tests.

    Those tests still exercise the real service stack, so their unique IDs are
    captured before execution and removed in teardown even if the test fails.
    Unmarked tests and normal development documents are never touched.
    """
    if request.node.get_closest_marker("isolated_document_corpus") is None:
        yield
        return
    db = SessionLocal()
    before = set(db.scalars(text("SELECT id FROM documents")).all())
    db.close()
    yield
    db = SessionLocal()
    try:
        created = set(db.scalars(text("SELECT id FROM documents")).all()) - before
        for document_id in created:
            params = {"document_id": document_id}
            minio_client.delete(str(document_id))
            db.execute(delete(DocumentAccessGrant).where(DocumentAccessGrant.document_id == document_id))
            db.execute(delete(GlobalDocumentAccess).where(GlobalDocumentAccess.document_id == document_id))
            db.execute(delete(LocalDocumentManifest).where(LocalDocumentManifest.document_id == document_id))
            db.execute(text("DELETE FROM indexing_jobs WHERE document_id = :document_id"), params)
            db.execute(text("DELETE FROM ingestion_jobs WHERE document_id = :document_id"), params)
            db.execute(text("DELETE FROM document_pages WHERE document_id = :document_id"), params)
            db.execute(delete(Document).where(Document.id == document_id))
        db.commit()
    finally:
        db.close()


def pytest_configure(config):
    config.addinivalue_line("markers", "real_auth: use real opaque-cookie authentication dependencies")
    config.addinivalue_line("markers", "isolated_document_corpus: tear down documents created by legacy integration tests")
