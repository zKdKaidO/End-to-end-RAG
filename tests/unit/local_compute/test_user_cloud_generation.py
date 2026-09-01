from __future__ import annotations

import json
import hashlib
import hmac
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from app.context.service import ContextBuilderService
from app.generation.client import LLMResult
from app.generation.exceptions import GenerationDependencyError
from app.generation.schemas import Usage
from app.local_compute.errors import LocalComputeError, LocalComputeErrorCode
from app.local_compute.generation import (
    GenerationProviderState,
    GenerationProviderType,
    GenerationRouter,
    GenerationRoutingPolicy,
    GenerationRoutingRequest,
    InMemoryUserCloudCredentialStore,
    LocalAnswerService,
    LocalGenerationProvider,
    OpenAICompatibleTransport,
    UnavailableUserCloudCredentialStore,
    UserCloudGenerationProvider,
    UserCloudProviderConfig,
    UserCloudProviderRegistry,
)
from app.local_compute.settings import LocalComputeSettings
from app.local_compute.api import create_local_compute_app
from app.local_compute.runtime import LocalComputeRuntime
from app.local_compute import api as local_api
from tests.context_doubles import CharacterTokenCounter
from tests.generation_doubles import FixedPromptCounter
from tests.unit.local_compute.test_generation import FakeLocalRetrieval, FakeOllamaClient, profile


CONFIG_ID = "00000000-0000-0000-0000-000000000099"
SECRET = "user-owned-test-secret-not-for-logs"


class FakeCloudTransport:
    def __init__(self, error: LocalComputeError | None = None, text: str = "[STATUS: ANSWERABLE]\nCloud answer [S1]"):
        self.error, self.text = error, text
        self.health_calls = self.generate_calls = 0
        self.last_messages = None

    async def health(self, model_id, secret):
        self.health_calls += 1
        assert secret == SECRET
        if self.error:
            raise self.error

    async def generate(self, messages, profile_value, model_id, secret):
        self.generate_calls += 1
        self.last_messages = messages
        assert secret == SECRET and model_id == "user-model-v1"
        if self.error:
            raise self.error
        return LLMResult(self.text, "stop", Usage(input_tokens=12, output_tokens=4, total_tokens=16))

    async def close(self):
        return None


def cloud_config(endpoint: str = "https://user-provider.example/v1") -> UserCloudProviderConfig:
    return UserCloudProviderConfig(CONFIG_ID, endpoint, "user-model-v1", "credential:one")


def cloud_registry(*, transport: FakeCloudTransport | None = None, development_mode: bool = True) -> UserCloudProviderRegistry:
    store, test_transport = InMemoryUserCloudCredentialStore({"credential:one": SECRET}), transport or FakeCloudTransport()
    return UserCloudProviderRegistry(store, development_mode=development_mode, profile=profile(), provider_factory=lambda config: UserCloudGenerationProvider(config, profile(), store, development_mode=development_mode, transport=test_transport))


def local_provider(*, ready: bool = True) -> LocalGenerationProvider:
    error = None if ready else GenerationDependencyError("x", "PROVIDER_UNAVAILABLE", "offline")
    return LocalGenerationProvider(profile(), "http://127.0.0.1:11434", client=FakeOllamaClient(health_error=error))


@pytest.mark.asyncio
async def test_routing_policies_are_explicit_and_platform_cloud_is_disabled():
    registry = cloud_registry(); registry.configure(cloud_config())
    router = GenerationRouter(local_provider(), registry)
    assert (await router.resolve(GenerationRoutingRequest())).provider_type == GenerationProviderType.LOCAL
    assert (await router.resolve(GenerationRoutingRequest(GenerationRoutingPolicy.USER_CLOUD_ONLY, CONFIG_ID))).provider_type == GenerationProviderType.USER_CLOUD
    assert (await router.resolve(GenerationRoutingRequest(GenerationRoutingPolicy.PREFER_LOCAL, CONFIG_ID))).provider_type == GenerationProviderType.LOCAL
    assert (await router.resolve(GenerationRoutingRequest(GenerationRoutingPolicy.PREFER_USER_CLOUD, CONFIG_ID))).provider_type == GenerationProviderType.USER_CLOUD
    with pytest.raises(LocalComputeError) as disabled:
        router.provider_for(GenerationProviderType.PLATFORM_CLOUD)
    assert disabled.value.code == LocalComputeErrorCode.PLATFORM_CLOUD_DISABLED


@pytest.mark.asyncio
async def test_paid_fallback_requires_explicit_permission_and_is_deterministic():
    registry = cloud_registry(); registry.configure(cloud_config())
    router = GenerationRouter(local_provider(ready=False), registry)
    with pytest.raises(LocalComputeError) as denied:
        await router.resolve(GenerationRoutingRequest(GenerationRoutingPolicy.PREFER_LOCAL, CONFIG_ID))
    assert denied.value.code == LocalComputeErrorCode.GENERATION_UNAVAILABLE
    decision = await router.resolve(GenerationRoutingRequest(GenerationRoutingPolicy.PREFER_LOCAL, CONFIG_ID, allow_user_cloud_fallback=True))
    assert decision.provider_type == GenerationProviderType.USER_CLOUD and decision.fallback_occurred
    with pytest.raises(LocalComputeError):
        await router.resolve(GenerationRoutingRequest(GenerationRoutingPolicy.USER_CLOUD_ONLY, None))

    unavailable_registry = cloud_registry(transport=FakeCloudTransport(LocalComputeError(LocalComputeErrorCode.USER_CLOUD_UNREACHABLE)))
    unavailable_registry.configure(cloud_config())
    prefer_cloud = GenerationRouter(local_provider(), unavailable_registry)
    with pytest.raises(LocalComputeError):
        await prefer_cloud.resolve(GenerationRoutingRequest(GenerationRoutingPolicy.PREFER_USER_CLOUD, CONFIG_ID))
    local_fallback = await prefer_cloud.resolve(GenerationRoutingRequest(GenerationRoutingPolicy.PREFER_USER_CLOUD, CONFIG_ID, allow_local_fallback=True))
    assert local_fallback.provider_type == GenerationProviderType.LOCAL and local_fallback.fallback_occurred


def test_config_security_and_production_secret_storage_fail_closed():
    for endpoint in ("file:///tmp/model", "ftp://provider.example", "javascript:alert(1)", "http://provider.example/v1", "https://user:pass@provider.example/v1"):
        with pytest.raises(LocalComputeError):
            cloud_config(endpoint).validate(development_mode=False)
    cloud_config("https://provider.example/v1").validate(development_mode=False)
    cloud_config("http://127.0.0.1:8080/v1").validate(development_mode=True)
    registry = UserCloudProviderRegistry(UnavailableUserCloudCredentialStore(), development_mode=False, profile=profile())
    with pytest.raises(LocalComputeError) as insecure:
        registry.configure(cloud_config())
    assert insecure.value.code == LocalComputeErrorCode.CREDENTIAL_STORE_UNAVAILABLE
    with pytest.raises(LocalComputeError):
        UserCloudProviderRegistry(InMemoryUserCloudCredentialStore({"credential:one": SECRET}), development_mode=False, profile=profile()).configure(cloud_config())
    rendered = repr(cloud_config().metadata())
    assert SECRET not in rendered and "credential:one" not in rendered and "user-provider.example" not in rendered
    with pytest.raises(LocalComputeError):
        GenerationRoutingRequest.from_values(policy="PREFER_LOCAL", allow_user_cloud_fallback="false")


@pytest.mark.asyncio
async def test_credentials_and_user_cloud_failures_are_typed_and_secret_free():
    missing = UserCloudGenerationProvider(cloud_config(), profile(), InMemoryUserCloudCredentialStore(), development_mode=True, transport=FakeCloudTransport())
    assert (await missing.availability()).state == GenerationProviderState.CREDENTIAL_UNAVAILABLE
    with pytest.raises(LocalComputeError) as absent:
        await missing.generate([])
    assert absent.value.code == LocalComputeErrorCode.CREDENTIAL_UNAVAILABLE
    for error, expected in ((LocalComputeError(LocalComputeErrorCode.USER_CLOUD_AUTH_FAILED, SECRET), GenerationProviderState.AUTH_FAILED), (LocalComputeError(LocalComputeErrorCode.USER_CLOUD_RATE_LIMITED, SECRET), GenerationProviderState.RATE_LIMITED), (LocalComputeError(LocalComputeErrorCode.GENERATION_TIMEOUT, SECRET), GenerationProviderState.DEGRADED)):
        subject = UserCloudGenerationProvider(cloud_config(), profile(), InMemoryUserCloudCredentialStore({"credential:one": SECRET}), development_mode=True, transport=FakeCloudTransport(error))
        availability = await subject.availability()
        assert availability.state == expected and SECRET not in str(availability.error_code)


class FakeProviderHandler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        self.server.hits.append(("GET", self.path, self.headers.get("Authorization")))
        if self.server.mode == "auth": return self._send(401, {"error": {"message": SECRET}})
        if self.server.mode == "rate": return self._send(429, {"error": {"message": SECRET}})
        if self.server.mode == "server": return self._send(500, {"error": {"message": SECRET}})
        if self.server.mode == "slow": time.sleep(0.15)
        return self._send(200, {"id": "user-model-v1"})

    def do_POST(self):
        size = int(self.headers.get("Content-Length", "0"))
        self.server.hits.append(("POST", self.path, self.headers.get("Authorization"), json.loads(self.rfile.read(size))))
        if self.server.mode == "malformed": return self._send(200, {"choices": []})
        return self._send(200, {"choices": [{"message": {"content": "[STATUS: ANSWERABLE]\\nExternal [S1]"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}})

    def log_message(self, *_args):
        return


@pytest.fixture
def fake_external_provider():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeProviderHandler)
    server.mode, server.hits = "success", []
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        yield server
    finally:
        server.shutdown(); server.server_close(); thread.join(2)


@pytest.mark.asyncio
async def test_reference_transport_uses_only_configured_endpoint_and_normalizes_output(fake_external_provider):
    endpoint = f"http://127.0.0.1:{fake_external_provider.server_port}/v1"
    subject = UserCloudGenerationProvider(cloud_config(endpoint), profile(), InMemoryUserCloudCredentialStore({"credential:one": SECRET}), development_mode=True, transport=OpenAICompatibleTransport(endpoint, 1))
    assert (await subject.availability()).state == GenerationProviderState.READY
    result = await subject.generate([{"role": "user", "content": "canonical context only"}])
    assert result.text.endswith("[S1]") and result.usage.total_tokens == 5
    assert fake_external_provider.hits[0][1] == "/v1/models/user-model-v1"
    assert fake_external_provider.hits[1][1] == "/v1/models/user-model-v1"
    assert fake_external_provider.hits[2][1] == "/v1/chat/completions"
    assert fake_external_provider.hits[2][3]["messages"][0]["content"] == "canonical context only"
    assert all(hit[2] == f"Bearer {SECRET}" for hit in fake_external_provider.hits)
    await subject.close()


@pytest.mark.asyncio
async def test_reference_transport_maps_auth_rate_timeout_5xx_and_malformed_without_leaks(fake_external_provider):
    endpoint = f"http://127.0.0.1:{fake_external_provider.server_port}/v1"
    for mode, expected in (("auth", LocalComputeErrorCode.USER_CLOUD_AUTH_FAILED), ("rate", LocalComputeErrorCode.USER_CLOUD_RATE_LIMITED), ("server", LocalComputeErrorCode.USER_CLOUD_UNREACHABLE), ("slow", LocalComputeErrorCode.GENERATION_TIMEOUT)):
        fake_external_provider.mode = mode
        transport = OpenAICompatibleTransport(endpoint, 0.02)
        with pytest.raises(LocalComputeError) as error:
            await transport.health("user-model-v1", SECRET)
        assert error.value.code == expected and SECRET not in str(error.value)
        await transport.close()
    fake_external_provider.mode = "malformed"
    transport = OpenAICompatibleTransport(endpoint, 1)
    await transport.health("user-model-v1", SECRET)
    with pytest.raises(LocalComputeError) as malformed:
        await transport.generate([], profile(), "user-model-v1", SECRET)
    assert malformed.value.code == LocalComputeErrorCode.INVALID_GENERATION_RESPONSE
    await transport.close()
    unreachable = OpenAICompatibleTransport("https://127.0.0.1:1/v1", 0.05)
    with pytest.raises(LocalComputeError) as refused:
        await unreachable.health("user-model-v1", SECRET)
    assert refused.value.code == LocalComputeErrorCode.USER_CLOUD_UNREACHABLE
    await unreachable.close()


@pytest.mark.asyncio
async def test_local_and_user_cloud_share_block6_finalization_and_local_only_never_calls_cloud():
    cloud_transport = FakeCloudTransport(); registry = cloud_registry(transport=cloud_transport); registry.configure(cloud_config())
    local_client = FakeOllamaClient(text="[STATUS: ANSWERABLE]\nLocal answer [S1]")
    router = GenerationRouter(LocalGenerationProvider(profile(), "http://127.0.0.1:11434", client=local_client), registry)
    def build():
        return LocalAnswerService(LocalComputeSettings(data_root=__import__("pathlib").Path("unused")), None, router, profile=profile(), retrieval_store=FakeLocalRetrieval(), context_builder=ContextBuilderService(CharacterTokenCounter()), prompt_counter=FixedPromptCounter(100))
    local = await build().answer(request_id="local", query_text="Mức phí là bao nhiêu?", document_ids=[str(uuid.UUID(int=2))])
    assert cloud_transport.generate_calls == 0
    cloud = await build().answer(request_id="cloud", query_text="Mức phí là bao nhiêu?", document_ids=[str(uuid.UUID(int=2))], routing=GenerationRoutingRequest(GenerationRoutingPolicy.USER_CLOUD_ONLY, CONFIG_ID))
    assert local.result.citations[0].source_id == cloud.result.citations[0].source_id == "S1"
    assert local.result.answerability_validation == cloud.result.answerability_validation
    assert local_client.generate_calls == 1 and cloud_transport.generate_calls == 1
    assert cloud.provider == GenerationProviderType.USER_CLOUD and cloud.model_id == "user-model-v1"
    unknown_transport = FakeCloudTransport(text="[STATUS: ANSWERABLE]\nUnknown [S99]")
    unknown_registry = cloud_registry(transport=unknown_transport); unknown_registry.configure(cloud_config())
    unknown_router = GenerationRouter(local_provider(), unknown_registry)
    unknown = await LocalAnswerService(LocalComputeSettings(data_root=__import__("pathlib").Path("unused")), None, unknown_router, profile=profile(), retrieval_store=FakeLocalRetrieval(), context_builder=ContextBuilderService(CharacterTokenCounter()), prompt_counter=FixedPromptCounter(100)).answer(request_id="unknown", query_text="Mức phí là bao nhiêu?", document_ids=[str(uuid.UUID(int=2))], routing=GenerationRoutingRequest(GenerationRoutingPolicy.USER_CLOUD_ONLY, CONFIG_ID))
    assert unknown.result.invalid_citations == ["S99"] and unknown.result.citations == []


def test_retrieval_only_endpoint_never_accesses_generation_router(tmp_path, monkeypatch):
    runtime = LocalComputeRuntime(LocalComputeSettings(data_root=tmp_path / "Compute", development_mode=True))
    runtime.start()
    class RetrievalOnly:
        def __init__(self, *_args): pass
        def query_document_set_with_diagnostics(self, query_text, document_ids):
            assert query_text == "evidence only" and document_ids is None
            return [], {"status": "NO_EXPANSION"}
    monkeypatch.setattr(local_api, "LocalRetrievalStore", RetrievalOnly)
    runtime.generation_router = lambda: (_ for _ in ()).throw(AssertionError("generation must not run"))
    try:
        client = TestClient(create_local_compute_app(runtime))
        session = client.post("/v1/sessions", headers={"Origin": runtime.settings.production_origin, "X-ZKD-Local-Grant": "development-test-grant"}).json()
        body = b'{"query_text":"evidence only"}'
        timestamp, nonce = str(int(time.time())), str(uuid.uuid4())
        signed = "|".join(("POST", "/v1/queries", timestamp, nonce, hashlib.sha256(body).hexdigest())).encode()
        headers = {"Origin": runtime.settings.production_origin, "Content-Type": "application/json", "X-ZKD-Local-Session": session["local_session_id"], "X-ZKD-Timestamp": timestamp, "X-ZKD-Nonce": nonce, "X-ZKD-MAC": hmac.new(session["session_key"].encode(), signed, hashlib.sha256).hexdigest(), "X-ZKD-Protocol-Version": runtime.settings.protocol_version}
        response = client.post("/v1/queries", content=body, headers=headers)
        assert response.status_code == 200 and response.json()["results"] == []
    finally:
        runtime.shutdown()


def test_answer_protocol_accepts_only_routing_identity_and_rejects_arbitrary_endpoint(tmp_path, monkeypatch):
    runtime = LocalComputeRuntime(LocalComputeSettings(data_root=tmp_path / "Compute", development_mode=True))
    runtime.start(); observed = {}
    class Response:
        def as_dict(self): return {"provider": "USER_CLOUD", "model_id": "user-model-v1", "result": {"status": "COMPLETED"}, "hierarchy": {}, "timings": {}}
    class AnswerService:
        def __init__(self, *_args): pass
        async def answer(self, **kwargs):
            observed.update(kwargs); return Response()
    monkeypatch.setattr(local_api, "LocalAnswerService", AnswerService)
    try:
        client = TestClient(create_local_compute_app(runtime))
        session = client.post("/v1/sessions", headers={"Origin": runtime.settings.production_origin, "X-ZKD-Local-Grant": "development-test-grant"}).json()
        body = json.dumps({"query_text": "answer", "routing_policy": "USER_CLOUD_ONLY", "provider_config_id": CONFIG_ID}).encode()
        timestamp, nonce = str(int(time.time())), str(uuid.uuid4())
        signed = "|".join(("POST", "/v1/answers", timestamp, nonce, hashlib.sha256(body).hexdigest())).encode()
        headers = {"Origin": runtime.settings.production_origin, "Content-Type": "application/json", "X-ZKD-Local-Session": session["local_session_id"], "X-ZKD-Timestamp": timestamp, "X-ZKD-Nonce": nonce, "X-ZKD-MAC": hmac.new(session["session_key"].encode(), signed, hashlib.sha256).hexdigest(), "X-ZKD-Protocol-Version": runtime.settings.protocol_version}
        assert client.post("/v1/answers", content=body, headers=headers).status_code == 200
        assert observed["routing"].provider_config_id == CONFIG_ID
        assert not hasattr(observed["routing"], "endpoint")
        unsafe_body = json.dumps({"query_text": "answer", "endpoint": "https://attacker.invalid"}).encode()
        unsafe_nonce = str(uuid.uuid4())
        unsafe_signed = "|".join(("POST", "/v1/answers", timestamp, unsafe_nonce, hashlib.sha256(unsafe_body).hexdigest())).encode()
        unsafe_headers = {**headers, "X-ZKD-Nonce": unsafe_nonce, "X-ZKD-MAC": hmac.new(session["session_key"].encode(), unsafe_signed, hashlib.sha256).hexdigest()}
        assert client.post("/v1/answers", content=unsafe_body, headers=unsafe_headers).status_code == 400
    finally:
        runtime.shutdown()
