from __future__ import annotations

import json
import os

import pytest

from app.local_compute.audit_log import LocalAuditLog
from app.local_compute.autostart import background_command
from app.local_compute.errors import LocalComputeError, LocalComputeErrorCode
from app.local_compute.pairing_uri import PairingUriError, parse_pairing_uri
from app.local_compute.product_paths import configure_managed_model_environment, packaged_resource_root, product_data_root
from app.local_compute.provisioning import E5ModelProvisioner, GenerationRuntimeManager
from app.local_compute.runtime import LocalComputeRuntime
from app.local_compute.settings import LocalComputeSettings
from app.local_compute.single_instance import AlreadyRunningError, WindowsSingleInstance


def test_single_instance_refuses_second_owner_and_releases_after_shutdown():
    first = WindowsSingleInstance("test-zkd-compute-product")
    second = WindowsSingleInstance("test-zkd-compute-product")
    first.acquire()
    with pytest.raises(AlreadyRunningError):
        second.acquire()
    first.release()
    second.acquire()
    second.release()


def test_product_data_and_managed_model_paths_do_not_require_developer_hf_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("ZKD_COMPUTE_DATA_ROOT", str(tmp_path / "data"))
    root = product_data_root()
    cache = configure_managed_model_environment(root)
    assert root == tmp_path / "data"
    assert cache == root / "models" / "huggingface"
    assert "huggingface" in str(cache)
    assert "Users" not in str(cache)
    assert cache.exists()
    assert os.environ["OLLAMA_BASE_URL"] == "http://127.0.0.1:11434"


def test_packaged_resource_resolution_uses_pyinstaller_root(tmp_path, monkeypatch):
    import app.local_compute.product_paths as paths
    monkeypatch.setattr(paths.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert packaged_resource_root() == tmp_path


def test_pairing_uri_accepts_only_expected_shape_and_redacts_token():
    request_id = "123e4567-e89b-12d3-a456-426614174000"
    pairing = parse_pairing_uri(f"zkd-compute://pair?request_id={request_id}&token=abcdefghijklmnop")
    assert pairing.request_id == request_id
    assert "abcdefghijklmnop" not in pairing.safe_description()
    for invalid in ("https://pair?request_id=x&token=abcdefghijklmnop", f"zkd-compute://pair?request_id={request_id}&token=abcdefghijklmnop&path=x", f"zkd-compute://pair?request_id={request_id}&token=bad"):
        with pytest.raises(PairingUriError):
            parse_pairing_uri(invalid)


def test_audit_log_rotates_and_never_contains_request_body_or_auth_material(tmp_path):
    audit = LocalAuditLog(tmp_path, max_bytes=1, backup_count=1)
    audit.record("request-1", "POST /v1/answers", 3, 200)
    audit.record("request-2", "GET /v1/runtime", 1, 200)
    joined = "".join(path.read_text(encoding="utf-8") for path in tmp_path.glob("runtime.jsonl*"))
    assert (tmp_path / "runtime.jsonl.1").exists()
    assert "session_key" not in joined and "PRIVATE_QUERY" not in joined and "authorization" not in joined.casefold()
    assert json.loads((tmp_path / "runtime.jsonl").read_text())['operation'] == "GET /v1/runtime"


def test_autostart_command_is_a_quoted_executable_only(tmp_path):
    executable = tmp_path / "ZKD-Compute.exe"
    assert background_command(executable) == f'"{executable}" --background'
    with pytest.raises(ValueError):
        background_command(tmp_path / "launcher.cmd")


def test_runtime_creates_product_data_directories_and_reconciles_durable_state(tmp_path):
    settings = LocalComputeSettings(data_root=tmp_path / "ZKD" / "Compute", development_mode=True, development_origins=("http://localhost:5173",))
    runtime = LocalComputeRuntime(settings)
    runtime.start()
    try:
        assert all(path.is_dir() for path in (settings.state_path, settings.config_path, settings.models_path, settings.documents_path, settings.artifacts_path, settings.logs_path, settings.tmp_path))
    finally:
        runtime.shutdown()


def test_missing_product_models_and_sidecar_fail_closed_without_download_or_execution(tmp_path):
    with pytest.raises(LocalComputeError) as embedding:
        E5ModelProvisioner(tmp_path / "models" / "huggingface").provision()
    assert embedding.value.code == LocalComputeErrorCode.MODEL_ARTIFACT_UNAVAILABLE
    with pytest.raises(LocalComputeError) as generation:
        GenerationRuntimeManager(tmp_path / "runtime").start()
    assert generation.value.code == LocalComputeErrorCode.GENERATION_UNAVAILABLE
