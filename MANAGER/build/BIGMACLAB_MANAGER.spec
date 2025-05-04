# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['C:/GitHub/BIGMACLAB/MANAGER/app/main.py'],
    pathex=['C:/GitHub/BIGMACLAB/MANAGER/app'],
    binaries=[],
    datas=[
        ('C:/GitHub/BIGMACLAB/MANAGER/app/assets', 'assets')
    ],
    hiddenimports=['seaborn.external.kde'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # 이 부분 추가하여 EXE에서 바이너리를 제외
    name='BIGMACLAB_MANAGER',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon='C:/GitHub/BIGMACLAB/MANAGER/source/exe_icon.ico'
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='BIGMACLAB_MANAGER'
)
