import uuid

import pytest
from redis import Redis

from app.auth.dependencies import get_current_principal
from app.auth.principal import Principal
from app.main import app
from app.core.config import settings


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


def pytest_configure(config):
    config.addinivalue_line("markers", "real_auth: use real opaque-cookie authentication dependencies")
