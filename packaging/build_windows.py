"""Deterministic onedir build entry point; release outputs remain untracked."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "build" / "windows"


def main() -> int:
    pyinstaller = shutil.which("pyinstaller")
    if not pyinstaller:
        print("PyInstaller is required: python -m pip install -r requirements-local-compute.txt", file=sys.stderr)
        return 2
    command = [pyinstaller, "--noconfirm", "--clean", "--distpath", str(DIST), "--workpath", str(ROOT / "build" / "pyinstaller-work"), "--specpath", str(ROOT / "packaging"), str(ROOT / "packaging" / "zkd_compute.spec")]
    return subprocess.run(command, cwd=ROOT, shell=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
