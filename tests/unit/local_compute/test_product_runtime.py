from __future__ import annotations

import json
import io
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from app.local_compute.audit_log import LocalAuditLog
from app.local_compute.autostart import background_command
from app.local_compute.errors import LocalComputeError, LocalComputeErrorCode
from app.local_compute.pairing_uri import PairingUriError, parse_pairing_uri
from app.local_compute.product_paths import local_model_cache_path, packaged_resource_root, product_data_root
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


def test_product_data_and_model_cache_paths_do_not_require_backend_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("ZKD_COMPUTE_DATA_ROOT", str(tmp_path / "data"))
    for name in (
        "DATABASE_URL",
        "REDIS_URL",
        "MINIO_ENDPOINT",
        "MINIO_ACCESS_KEY",
        "MINIO_SECRET_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    prior_embedding_cache = os.environ.get("EMBEDDING_MODEL_CACHE_DIR")
    root = product_data_root()
    cache = local_model_cache_path()
    assert root == tmp_path / "data"
    assert cache.name == "hub"
    assert "huggingface" in str(cache)
    assert os.environ.get("EMBEDDING_MODEL_CACHE_DIR") == prior_embedding_cache
    for name in ("DATABASE_URL", "REDIS_URL", "MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY"):
        assert name not in os.environ


def test_launcher_import_isolated_from_production_settings(tmp_path):
    environment = os.environ.copy()
    environment["ZKD_COMPUTE_DATA_ROOT"] = str(tmp_path / "Compute")
    for name in (
        "DATABASE_URL",
        "REDIS_URL",
        "MINIO_ENDPOINT",
        "MINIO_ACCESS_KEY",
        "MINIO_SECRET_KEY",
    ):
        environment.pop(name, None)

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import app.local_compute.production_launcher; "
                "import app.local_compute.server; "
                "import app.local_compute.api; "
                "assert 'app.core.config' not in sys.modules"
            ),
        ],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[3]),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


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


def test_developer_answer_pipeline_uses_stdin_all_document_shape_and_never_prints_content(tmp_path, monkeypatch, capsys):
    import app.local_compute.production_launcher as launcher

    captured: dict[str, object] = {}
    expected_settings = SimpleNamespace(
        catalog_path="catalog-path", logs_path=tmp_path / "logs"
    )

    class FakeRuntime:
        def __init__(self, settings):
            assert settings is expected_settings

        def generation_router(self):
            return SimpleNamespace(local_provider=SimpleNamespace(profile="profile"))

    class FakeService:
        def __init__(self, settings, catalog, router, *, profile):
            assert (settings, catalog, router.local_provider.profile, profile) == (
                expected_settings,
                "catalog",
                "profile",
                "profile",
            )

        async def answer(self, **kwargs):
            captured.update(kwargs)
            kwargs["stage_reporter"]("answers_context_done", "ANYIO_THREADPOOL")
            return SimpleNamespace(
                answer_mode="EXPLORE",
                as_dict=lambda: {"private_answer_text": "must not print"},
                result=SimpleNamespace(status=SimpleNamespace(value="COMPLETED")),
            )

    payload = {
        "query_text": "Private diagnostic question",
        "document_ids": None,
        "answer_mode": "EXPLORE",
    }
    monkeypatch.setattr(launcher, "build_settings", lambda: expected_settings)
    monkeypatch.setattr(launcher, "LocalComputeRuntime", FakeRuntime)
    monkeypatch.setattr(launcher, "LocalCatalog", lambda _path: "catalog")
    monkeypatch.setattr("app.local_compute.generation.LocalAnswerService", FakeService)
    monkeypatch.setattr(launcher.sys, "stdin", SimpleNamespace(buffer=io.BytesIO(json.dumps(payload).encode("utf-8"))))

    assert launcher.run_developer_answer_pipeline() == 0
    output = json.loads(capsys.readouterr().out)
    assert output == {
        "diagnostic": "developer_answer_pipeline",
        "status": "PASS",
        "answer_mode": "EXPLORE",
        "stages": [
            "answers_context_done",
            "answers_serialization_begin",
            "answers_serialization_done",
            "answers_response_ready",
        ],
        "response_serializable": True,
        "generation_status": "COMPLETED",
    }
    assert captured["document_ids"] is None
    assert captured["query_text"] == payload["query_text"]


def test_developer_answer_pipeline_accepts_windowed_process_local_payload(monkeypatch):
    import base64
    import app.local_compute.production_launcher as launcher

    payload = b'{"query_text":"q","document_ids":null,"answer_mode":"EXACT"}'
    monkeypatch.setattr(launcher.sys, "stdin", None)
    monkeypatch.setenv(
        launcher._DIAGNOSTIC_PAYLOAD_ENV,
        base64.b64encode(payload).decode("ascii"),
    )

    assert launcher._read_developer_diagnostic_payload() == payload
    assert launcher._DIAGNOSTIC_PAYLOAD_ENV not in os.environ


class _BrokenConsoleStream:
    closed = False

    def write(self, _value):
        raise OSError(22, "Invalid argument")

    def flush(self):
        raise OSError(22, "Invalid argument")

    def isatty(self):
        raise OSError(22, "Invalid argument")

    def fileno(self):
        raise OSError(22, "Invalid argument")


@pytest.mark.parametrize("attribute", ("stdout", "stderr"))
def test_windowed_launcher_replaces_missing_standard_streams(monkeypatch, attribute):
    import app.local_compute.production_launcher as launcher

    original_count = len(launcher._NO_CONSOLE_STREAM_HANDLES)
    with monkeypatch.context() as patch:
        patch.setattr(launcher.sys, "frozen", True, raising=False)
        patch.setattr(launcher.sys, "platform", "win32")
        patch.setattr(launcher.sys, attribute, None)
        launcher._ensure_standard_streams_for_windowed_runtime()
        replacement = getattr(launcher.sys, attribute)
        assert replacement is not None
        assert launcher._stream_is_usable(replacement)

    added = launcher._NO_CONSOLE_STREAM_HANDLES[original_count:]
    for handle in added:
        handle.close()
    del launcher._NO_CONSOLE_STREAM_HANDLES[original_count:]


def test_windowed_launcher_replaces_existing_invalid_console_handles(monkeypatch):
    import app.local_compute.production_launcher as launcher

    original_count = len(launcher._NO_CONSOLE_STREAM_HANDLES)
    with monkeypatch.context() as patch:
        patch.setattr(launcher.sys, "frozen", True, raising=False)
        patch.setattr(launcher.sys, "platform", "win32")
        patch.setattr(launcher.sys, "stdout", _BrokenConsoleStream())
        patch.setattr(launcher.sys, "stderr", _BrokenConsoleStream())
        launcher._ensure_standard_streams_for_windowed_runtime()
        assert launcher._stream_is_usable(launcher.sys.stdout)
        assert launcher._stream_is_usable(launcher.sys.stderr)
        assert launcher.sys.stdout is not launcher.sys.stderr

    added = launcher._NO_CONSOLE_STREAM_HANDLES[original_count:]
    for handle in added:
        handle.close()
    del launcher._NO_CONSOLE_STREAM_HANDLES[original_count:]


def test_frozen_model_progress_is_disabled_before_tqdm_can_write(monkeypatch):
    import huggingface_hub.utils as hf_utils
    from tqdm import tqdm
    from transformers.utils import logging as transformers_logging
    import app.local_compute.production_launcher as launcher

    called = {"hf": False, "transformers": False}
    with monkeypatch.context() as patch:
        patch.setattr(launcher.sys, "frozen", True, raising=False)
        patch.setattr(launcher.sys, "platform", "win32")
        patch.setattr(launcher.sys, "stdout", _BrokenConsoleStream())
        patch.setattr(launcher.sys, "stderr", _BrokenConsoleStream())
        patch.setattr(hf_utils, "disable_progress_bars", lambda: called.__setitem__("hf", True))
        patch.setattr(transformers_logging, "disable_progress_bar", lambda: called.__setitem__("transformers", True))
        launcher._ensure_standard_streams_for_windowed_runtime()
        launcher._disable_frozen_model_progress()
        list(tqdm(range(1), file=launcher.sys.stderr))

    assert called == {"hf": True, "transformers": True}
    assert os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] == "1"
    assert os.environ["TQDM_DISABLE"] == "1"


def test_fatal_launcher_reporting_survives_unusable_standard_error(monkeypatch):
    import app.local_compute.production_launcher as launcher

    recorded = []
    with monkeypatch.context() as patch:
        patch.setattr(launcher.sys, "stderr", _BrokenConsoleStream())
        patch.setattr(launcher, "bootstrap_log", lambda stage, error=None, **_: recorded.append((stage, type(error).__name__)))
        assert launcher.main(["--pair-uri", "not-a-pairing-uri"]) == 2

    assert recorded == [("launcher_enter", "NoneType"), ("pairing_uri_error", "PairingUriError")]


def test_standard_stream_guard_leaves_normal_development_streams_unchanged(monkeypatch):
    import app.local_compute.production_launcher as launcher

    original_stdout, original_stderr = launcher.sys.stdout, launcher.sys.stderr
    with monkeypatch.context() as patch:
        patch.setattr(launcher.sys, "frozen", False, raising=False)
        launcher._ensure_standard_streams_for_windowed_runtime()
    assert launcher.sys.stdout is original_stdout
    assert launcher.sys.stderr is original_stderr
