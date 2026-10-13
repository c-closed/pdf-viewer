# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: 가벼운 PDF 뷰어 (onedir: 폴더 형태, 시작 속도 우선)."""

a = Analysis(
    ["pdf_viewer.py"],
    pathex=["."],
    binaries=[],
    datas=[("icon.ico", ".")],
    hiddenimports=["pypdfium2", "PIL", "tkinterdnd2", "pikepdf"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "numpy",
        "matplotlib",
        "scipy",
        "pandas",
        "PyQt5",
        "PySide6",
        "reportlab",
        "pypdf",
        "cryptography",
        "test",
        "unittest",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PDFViewer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="icon.ico",
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PDFViewer",
)
