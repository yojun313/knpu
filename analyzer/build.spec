# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],  # 실행 진입점
    pathex=['./analyzer'],  # main.py가 있는 디렉토리
    binaries=[],
    datas=[
        ('pandasgui/resources', 'pandasgui/resources'),
        ('pandasgui/widgets', 'pandasgui/widgets'),

        # 데이터 분석 관련
        ('C:/Users/skroh/AppData/Local/Programs/Python/Python312/Lib/site-packages/numpy', 'numpy'),
        ('C:/Users/skroh/AppData/Local/Programs/Python/Python312/Lib/site-packages/plotly', 'plotly'),
        ('C:/Users/skroh/AppData/Local/Programs/Python/Python312/Lib/site-packages/wordcloud', 'wordcloud'),
        ('C:/Users/skroh/AppData/Local/Programs/Python/Python312/Lib/site-packages/pyarrow', 'pyarrow'),
        ('C:/Users/skroh/AppData/Local/Programs/Python/Python312/Lib/site-packages/astor', 'astor'),
        ('C:/Users/skroh/AppData/Local/Programs/Python/Python312/Lib/site-packages/pynput', 'pynput'),
        ('C:/Users/skroh/AppData/Local/Programs/Python/Python312/Lib/site-packages/IPython', 'IPython'),
        ('C:/Users/skroh/AppData/Local/Programs/Python/Python312/Lib/site-packages/setuptools', 'setuptools'),
        ('C:/Users/skroh/AppData/Local/Programs/Python/Python312/Lib/site-packages/qtstylish', 'qtstylish'),

        # Windows 전용 모듈
        ('C:/Users/skroh/AppData/Local/Programs/Python/Python312/Lib/site-packages/pywin32_system32', 'pywin32_system32'),
    ],
    hiddenimports=[
        # 기본 GUI 관련
        'PyQt5',
        'PyQt5.sip',
        'PyQtWebEngine',
        # 데이터 분석 관련
        'pandas',
        'numpy',
        'plotly',
        'wordcloud',
        'pyarrow',
        'astor',
        'typing_extensions',
        'pynput',
        'IPython',
        'setuptools',
        # Windows 관련 (조건부)
        'pywin32',
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
