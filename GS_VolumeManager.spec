# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = ['gsVolClient', 'mount_services']

# Pull in requests and its runtime deps
for pkg in ('requests', 'urllib3', 'certifi', 'charset_normalizer', 'idna'):
    d, b, h = collect_all(pkg)
    datas    += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ['gs_vol_gui.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['flask', 'werkzeug', 'zeroconf'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='GS_VolumeManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                   # no black console window on Windows
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
