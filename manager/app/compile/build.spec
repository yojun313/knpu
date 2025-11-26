import os, platform

ROOT_PATH = os.path.abspath(os.getcwd())
APP_PATH = os.path.join(ROOT_PATH, "..")
ASSETS_PATH = os.path.join(APP_PATH, "assets")

ICON_FILE = "exe_icon.ico" if platform.system() == "Windows" else "app_icon.icns"
ICON_PATH = os.path.join(ASSETS_PATH, ICON_FILE)

MAIN_SCRIPT = os.path.join(APP_PATH, "main.py")

a = Analysis(
    [MAIN_SCRIPT],
    pathex=[APP_PATH],
    binaries=[],
    datas=[
        (ASSETS_PATH, 'assets')
    ],
    hiddenimports=[
        'seaborn.external.kde',
        'requests_toolbelt',
        'numpy',
        'pandas'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=True,
    optimize=2
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=False,
    name='MANAGER',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=ICON_PATH
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MANAGER'
)
