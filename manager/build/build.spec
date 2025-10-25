# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['C:/GitHub/knpu/manager/app/main.py'],
    pathex=['C:/GitHub/knpu/manager/app'],
    binaries=[],
    datas=[
        ('C:/GitHub/knpu/manager/app/assets', 'assets')
    ],
    hiddenimports=['seaborn.external.kde', 'requests_toolbelt'],
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
    name='MANAGER',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon='C:/GitHub/knpu/manager/app/assets/exe_icon.ico'
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
