from threading import Event
from types import SimpleNamespace

from app.local_compute.tray import WindowsTray
from app.local_compute.single_instance import AlreadyRunningError, WindowsSingleInstance


def test_tray_maps_runtime_and_model_state_without_a_duplicate_state_machine(tmp_path):
    runtime = SimpleNamespace(
        state=SimpleNamespace(value="READY"),
        capabilities=lambda: {"generation": "READY"},
    )
    tray = WindowsTray(runtime, logs_path=tmp_path, open_url="https://rag.zkd.id.vn", quit_requested=Event(), restart_requested=Event())
    assert tray.status_text() == "ZKD Compute — Ready"
    runtime.capabilities = lambda: {"generation": "MODEL_UNAVAILABLE"}
    assert tray.status_text() == "ZKD Compute — Model unavailable"


def test_tray_actions_are_events_not_second_processes(tmp_path):
    quit_requested, restart_requested = Event(), Event()
    runtime = SimpleNamespace(state=SimpleNamespace(value="READY"), capabilities=lambda: {"generation": "READY"})
    tray = WindowsTray(runtime, logs_path=tmp_path, open_url="https://rag.zkd.id.vn", quit_requested=quit_requested, restart_requested=restart_requested)
    tray.quit_requested.set(); tray.restart_requested.set()
    assert quit_requested.is_set() and restart_requested.is_set()


def test_second_instance_is_rejected_before_runtime_or_tray_startup():
    first = WindowsSingleInstance(name="test-zkd-compute-secondary")
    first.acquire()
    try:
        second = WindowsSingleInstance(name="test-zkd-compute-secondary")
        try:
            second.acquire()
        except AlreadyRunningError:
            pass
        else:  # pragma: no cover - test must fail on a broken ownership lock
            raise AssertionError("second instance acquired the process mutex")
    finally:
        first.release()
