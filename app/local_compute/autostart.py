"""User-level Windows autostart abstraction; never uses a system service."""

from __future__ import annotations

import os
from pathlib import Path


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "ZKD Compute"


def background_command(executable: Path) -> str:
    if not executable.is_absolute() or executable.suffix.casefold() != ".exe":
        raise ValueError("ZKD_COMPUTE_AUTOSTART_EXECUTABLE_INVALID")
    return f'"{executable}" --background'


class WindowsAutostart:
    def register(self, executable: Path) -> None:
        if os.name != "nt":
            raise RuntimeError("ZKD_COMPUTE_AUTOSTART_WINDOWS_REQUIRED")
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, background_command(executable))

    def unregister(self) -> None:
        if os.name != "nt":
            return
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            return
