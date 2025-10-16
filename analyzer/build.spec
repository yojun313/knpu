# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],  # 실행 진입점
    pathex=['./analyzer'],  # main.py가 있는 디렉토리
    binaries=[],
    datas=[
        ('pandasgui/resources', 'pandasgui/resources'),
        ('pandasgui/widgets', 'pandasgui/widgets'),
        ('C:/Users/skroh/AppData/Local/Programs/Python/Python312/Lib/site-packages/qtstylish', 'qtstylish'),
    ],
    hiddenimports=[
        # pandasgui 내부에서 동적으로 import되는 모듈이 있을 수 있으므로 필요시 여기에 추가
        'PyQt5',
        'pandas',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ANALYZER',       # 생성될 exe 파일 이름
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,           # 콘솔창 숨기고 싶다면 False로
    icon='C:/GitHub/knpu/analyzer/pandasgui/resources/images/icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ANALYZER'
)
