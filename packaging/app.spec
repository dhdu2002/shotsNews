# -*- mode: python ; coding: utf-8 -*-

"""Windows MVP용 PyInstaller 스펙 파일."""

from pathlib import Path


ROOT = Path(SPECPATH).parent
SRC = ROOT / "src"

datas = [
    (str(ROOT / "config" / "app.example.env"), "config"),
]

hiddenimports = [
    "apscheduler.schedulers.background",
    "daily_issue_app",
    "daily_issue_app.bootstrap",
    "daily_issue_app.infrastructure.db.schema",
    "daily_issue_app.main",
    "feedparser",
    "httpx",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "ui",
    "ui.app",
]


a = Analysis(
    [str(ROOT / "scripts" / "run_desktop.py")],
    pathex=[str(SRC), str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="shotsNews",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="shotsNews",
)
