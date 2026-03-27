# -*- mode: python ; coding: utf-8 -*-
import json
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT_DIR = Path.cwd()
APP_VERSION = json.loads((ROOT_DIR / "version.json").read_text(encoding="utf-8")).get("version", "1.0.0")

datas = []
binaries = []
hiddenimports = []
tmp_ret = collect_all('pygame')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
datas += [
    (str(ROOT_DIR / "Football Game.py"), "."),
    (str(ROOT_DIR / "version.json"), "."),
]


a = Analysis(
    [str(ROOT_DIR / 'launcher.py')],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FC Legends',
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
    icon=[str(ROOT_DIR / 'assets/fc_legends.icns')],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FC Legends',
)
app = BUNDLE(
    coll,
    name='FC Legends.app',
    icon=str(ROOT_DIR / 'assets/fc_legends.icns'),
    bundle_identifier='com.fclegends.app',
    info_plist={
        "CFBundleDisplayName": "FC Legends",
        "CFBundleName": "FC Legends",
        "CFBundleIdentifier": "com.fclegends.app",
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundleVersion": APP_VERSION,
        "NSHighResolutionCapable": True,
    },
)
