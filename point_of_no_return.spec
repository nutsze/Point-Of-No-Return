# -*- mode: python ; coding: utf-8 -*-

# В onefile-EXE входят только рабочие ресурсы. Неоптимизированные PNG-копии
# остаются в архиве исходников и не замедляют запуск Windows-версии.
datas = [
    ("data", "data"),
    ("assets/credits.json", "assets"),
    ("assets/fonts", "assets/fonts"),
    ("assets/portraits", "assets/portraits"),
    ("assets/locations", "assets/locations"),
    ("assets/events", "assets/events"),
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PointOfNoReturn2030",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/app.ico",
)
