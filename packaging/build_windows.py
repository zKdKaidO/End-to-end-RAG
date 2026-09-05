"""Deterministic onedir build entry point; release outputs remain untracked."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "build" / "windows"
WORK = ROOT / "build" / "pyinstaller-work"
SPEC = ROOT / "packaging" / "zkd_compute.spec"


def main() -> int:
    pyinstaller = shutil.which("pyinstaller")

    if not pyinstaller:
        print(
            "PyInstaller is required: "
            "python -m pip install -r requirements-local-compute.txt",
            file=sys.stderr,
        )
        return 2

    DIST.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)

    launcher = (
        ROOT
        / "app"
        / "local_compute"
        / "production_launcher.py"
    )

    if not launcher.is_file():
        print(
            f"Production launcher not found: {launcher}",
            file=sys.stderr,
        )
        return 3

    env = os.environ.copy()
    env["ZKD_BUILD_ROOT"] = str(ROOT)

    command = [
        pyinstaller,
        "--noconfirm",
        "--clean",
        "--distpath",
        str(DIST),
        "--workpath",
        str(WORK),
        str(SPEC),
    ]

    print("Building ZKD Compute...")
    print("Repository root:", ROOT)
    print("PyInstaller:", pyinstaller)
    print("Spec:", SPEC)
    print("Launcher:", launcher)
    print("Dist:", DIST)

    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        shell=False,
    )

    if completed.returncode != 0:
        return completed.returncode

    executable = (
        DIST
        / "ZKD-Compute"
        / "ZKD-Compute.exe"
    )

    if not executable.is_file():
        print(
            f"Build finished but executable was not found: {executable}",
            file=sys.stderr,
        )
        return 4

    print()
    print("ZKD_COMPUTE_BUILD_PASS")
    print("EXE =", executable)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())