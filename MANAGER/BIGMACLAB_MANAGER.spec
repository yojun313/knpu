# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['C:/GitHub/BIGMACLAB/MANAGER/BIGMACLAB_MANAGER.py'],
    pathex=[],
    binaries=[],
    datas=[('C:/GitHub/BIGMACLAB/MANAGER/source/BIGMACLAB_MANAGER_GUI.ui', 'source'),
        ('C:/GitHub/BIGMACLAB/MANAGER/source/encrypted_env', 'source'),
        ('C:/GitHub/BIGMACLAB/MANAGER/source/env.key', 'source'),
        ('C:/GitHub/BIGMACLAB/MANAGER/source/exe_icon.png', 'source'),
        ('C:/GitHub/BIGMACLAB/MANAGER/source/setting.png', 'source'),
        ('C:/GitHub/BIGMACLAB/MANAGER/source/search.png', 'source'),
        ('C:/GitHub/BIGMACLAB/MANAGER/source/microphone.png', 'source'),
        ('C:/GitHub/BIGMACLAB/MANAGER/source/malgun.ttf', 'source')
    ],
    hiddenimports=['seaborn.external.kde', 'connectorx'],
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
