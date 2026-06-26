# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.building.build_main import Analysis, COLLECT, EXE, PYZ
from PyInstaller.building.osx import BUNDLE
from PyInstaller.utils.hooks import collect_all

block_cipher = None
datas = [
    ("app.py", "."),
    ("pwa.py", "."),
    (".streamlit", ".streamlit"),
    ("static", "static"),
]

hiddenimports = []
for package in ("streamlit", "pandas", "openpyxl", "PIL", "altair", "pyarrow"):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
        datas += pkg_datas
        hiddenimports += pkg_hidden
    except Exception:
        hiddenimports.append(package)

a = Analysis(
    ["desktop.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports + ["webview"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Sky Order Converter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Sky Order Converter",
)
app = BUNDLE(
    coll,
    name="Sky Order Converter.app",
    icon=None,
    bundle_identifier="com.sky.orderconverter",
)
