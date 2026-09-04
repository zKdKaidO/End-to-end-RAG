"""Windows per-user runtime ownership using a named mutex."""

from __future__ import annotations

import ctypes
import os
import threading


class AlreadyRunningError(RuntimeError):
    pass


class WindowsSingleInstance:
    """A non-stale ownership boundary. Windows releases it on process exit."""

    _fallback_guard = threading.Lock()
    _fallback_names: set[str] = set()

    def __init__(self, name: str = "Local\\ZKD.Compute.Runtime.V1") -> None:
        self.name = name
        self._handle = None
        self._fallback_owned = False

    def acquire(self) -> None:
        if self._handle is not None or self._fallback_owned:
            return
        if os.name == "nt":
            kernel32 = ctypes.windll.kernel32
            kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
            kernel32.CreateMutexW.restype = ctypes.c_void_p
            handle = kernel32.CreateMutexW(None, False, self.name)
            if not handle:
                raise RuntimeError("ZKD_COMPUTE_MUTEX_CREATE_FAILED")
            if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
                kernel32.CloseHandle(handle)
                raise AlreadyRunningError("ZKD_COMPUTE_ALREADY_RUNNING")
            self._handle = handle
            return
        # Test/developer fallback only; production packaging targets Windows.
        with self._fallback_guard:
            if self.name in self._fallback_names:
                raise AlreadyRunningError("ZKD_COMPUTE_ALREADY_RUNNING")
            self._fallback_names.add(self.name)
            self._fallback_owned = True

    def release(self) -> None:
        if self._handle is not None:
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None
        if self._fallback_owned:
            with self._fallback_guard:
                self._fallback_names.discard(self.name)
            self._fallback_owned = False

    def __enter__(self) -> "WindowsSingleInstance":
        self.acquire()
        return self

    def __exit__(self, *_args) -> None:
        self.release()
