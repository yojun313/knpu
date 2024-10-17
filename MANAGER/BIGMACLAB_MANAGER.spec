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
    upx=False,  # UPX 압축 비활성화
    upx_exclude=['Qt5Core.dll', 'Qt5Gui.dll', 'Qt5Widgets.dll'],  # Qt 관련 파일 압축 제외
    runtime_tmpdir='C:/path/to/tempdir',  # 임시 디렉토리 지정
    console=True,  # 디버깅을 위한 콘솔 창 열기
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon= 'C:/GitHub/BIGMACLAB/MANAGER/exe_icon.ico'
)
