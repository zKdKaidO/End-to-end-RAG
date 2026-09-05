# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


root_value = os.environ.get("ZKD_BUILD_ROOT")

if not root_value:
    raise RuntimeError(
        "ZKD_BUILD_ROOT is required by the ZKD Compute packaging spec."
    )

ROOT = Path(root_value).resolve()

launcher = (
    ROOT
    / "app"
    / "local_compute"
    / "production_launcher.py"
)

prompts = (
    ROOT
    / "app"
    / "prompts"
)

if not launcher.is_file():
    raise RuntimeError(
        f"Production launcher not found: {launcher}"
    )

if not prompts.is_dir():
    raise RuntimeError(
        f"Prompt resource directory not found: {prompts}"
    )


hiddenimports = []

for package in (
    "app.local_compute",
    "app.pdf",
    "app.processing",
    "app.context",
    "app.generation",
    "app.indexing",
):
    hiddenimports.extend(
        collect_submodules(package)
    )


a = Analysis(
    [str(launcher)],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (
            str(prompts),
            "app/prompts",
        )
    ],
    hiddenimports=hiddenimports,
    excludes=[
        "alembic",
        "minio",
        "psycopg2",
        "redis",
        "rq",
        "sqlalchemy",
        "pgvector",
    ],
    noarchive=False,
)


pyz = PYZ(
    a.pure
)


exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ZKD-Compute",
    console=False,
    uac_admin=False,
)


coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="ZKD-Compute",
)