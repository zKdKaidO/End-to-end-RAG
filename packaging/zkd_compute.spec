# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent.parent
hiddenimports = []
for package in ("app.local_compute", "app.pdf", "app.processing", "app.context", "app.generation", "app.indexing"):
    hiddenimports.extend(collect_submodules(package))

a = Analysis(
    [str(ROOT / "app" / "local_compute" / "production_launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / "app" / "prompts"), "app/prompts")],
    hiddenimports=hiddenimports,
    excludes=["alembic", "minio", "psycopg2", "redis", "rq", "sqlalchemy", "pgvector"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ZKD-Compute", console=False, uac_admin=False)
coll = COLLECT(exe, a.binaries, a.datas, name="ZKD-Compute")
