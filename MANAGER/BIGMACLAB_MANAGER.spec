# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:/GitHub/BIGMACLAB/MANAGER/BIGMACLAB_MANAGER.py'],
    pathex=[],
    binaries=[],
    datas=[('C:/GitHub/BIGMACLAB/MANAGER/BIGMACLAB_MANAGER_GUI.ui', '.')],
    hiddenimports=['seaborn.external.kde', 'matplotlib.backends.backend_qt5agg', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets'],
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
    a.binaries,
    a.datas,
    [],
    name='BIGMACLAB_MANAGER',
    debug=False,
    bootloader_ignore_signals=True,
    strip=False,
    upx=False,
    upx_exclude=['Qt5Core.dll', 'Qt5Gui.dll', 'Qt5Widgets.dll'],
    runtime_tmpdir='C:/path/to/tempdir',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon= 'C:/GitHub/BIGMACLAB/MANAGER/exe_icon.ico'
)
