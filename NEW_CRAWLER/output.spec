# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['C:/GitHub/BIGMACLAB/NEW_CRAWLER/CrawlerManager_gui.py'],
    pathex=[],  # 여기에 필요한 추가 경로를 명시
    binaries=[],
    datas=[],
    hiddenimports=[],  # 자동으로 감지되지 않는 모듈 추가
    hookspath=[],
    hooksconfig={},
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
    name='CRAWLER_MANAGER',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI 프로그램인 경우 False로 설정
    icon='C:/GitHub/BIGMACLAB_WEB/public/assets/img/bigmaclab_logo_favicon.ico'
)
