# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — Turkify motoru (turkify-engine), onedir.

Derleme: ``macos/packaging/build_engine.sh``. Çıktı:
``macos/packaging/dist/turkify-engine/`` (içinde ``turkify-engine`` çalıştırılabilir).
Bkz. ADR 0009.
"""

from PyInstaller.utils.hooks import collect_all, collect_data_files

# turkify paket verisi (data/*.txt, prompts/*.txt) — importlib.resources okuyacak.
datas = collect_data_files("turkify")
binaries = []
hiddenimports = []

# Tier 2 (zeyrek) kuruluysa tüm modül + verisini topla; değilse Tier 1+3 ile devam.
try:
    z_datas, z_binaries, z_hidden = collect_all("zeyrek")
    datas += z_datas
    binaries += z_binaries
    hiddenimports += z_hidden
except Exception:
    pass

a = Analysis(
    ["turkify_engine.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
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
    name="turkify-engine",
    console=True,            # alt süreç olarak boru ile çalışır; pencere açmaz
    target_arch=None,        # evrensel için "universal2" (universal Python gerekir)
    codesign_identity=None,  # imzalama ayrı adımda (bkz. packaging/README.md)
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="turkify-engine",
)
