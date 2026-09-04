"""Build the per-user Inno Setup installer when the compiler is installed."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def find_iscc() -> str | None:
    if found := shutil.which("ISCC"):
        return found
    candidates = [Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe", Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 6" / "ISCC.exe"]
    return next((str(path) for path in candidates if path.is_file()), None)


def main() -> int:
    compiler = find_iscc()
    if not compiler:
        print("Inno Setup 6 ISCC.exe is required to produce ZKD-Compute-Setup.exe.", file=sys.stderr)
        return 2
    return subprocess.run([compiler, str(ROOT / "installer" / "ZKD-Compute.iss")], cwd=ROOT, shell=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
