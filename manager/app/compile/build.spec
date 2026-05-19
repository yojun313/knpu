import os
import platform
import glob
import re
from PyInstaller.utils.hooks import collect_submodules

COMPILE_PATH = os.path.dirname(os.path.abspath(__file__))
ROOT_PATH = os.path.abspath(os.path.join(COMPILE_PATH, ".."))
APP_PATH = ROOT_PATH
ASSETS_PATH = os.path.join(APP_PATH, "assets")

ICON_FILE = "exe_icon.ico" if platform.system() == "Windows" else "app_icon.icns"
ICON_PATH = os.path.join(ASSETS_PATH, ICON_FILE)

MAIN_SCRIPT = os.path.join(APP_PATH, "main.py")

def get_used_modules(target_dir):
    used = set(['seaborn', 'requests_toolbelt', 'numpy', 'pandas', 'jinja2']) 
    py_files = glob.glob(os.path.join(target_dir, "**", "*.py"), recursive=True)
    
    import_regex = re.compile(r'^\s*(?:import|from)\s+([a-zA-Z0-9_]+)')
    
    for fpath in py_files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                for line in f:
                    match = import_regex.match(line)
                    if match:
                        used.add(match.group(1))
        except Exception:
            continue
    return used

def get_all_site_packages():
    project_root = os.path.abspath(os.path.join(ROOT_PATH, "..", ".."))
    venv_paths = [
        os.path.join(project_root, ".venv", "Lib", "site-packages"),
        os.path.join(ROOT_PATH, ".venv", "Lib", "site-packages"),
        os.path.join(APP_PATH, ".venv", "Lib", "site-packages")
    ]
    all_modules = set()
    for vp in venv_paths:
        if os.path.exists(vp):
            for item in os.listdir(vp):
                if item.endswith(('.py', '.egg-info', '.dist-info')):
                    name = item.split('.')[0]
                else:
                    name = item
                if name and not name.startswith('_'):
                    all_modules.add(name)
    return all_modules

used_modules = get_used_modules(APP_PATH)
all_installed = get_all_site_packages()
dynamic_excludes = list(all_installed - used_modules)

safeguards = ['setuptools', 'pkg_resources', 'pip', 'uv', 'PyInstaller']
dynamic_excludes = [m for m in dynamic_excludes if m not in safeguards]

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
    excludes=dynamic_excludes, 
    noarchive=False,
    optimize=2                 
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
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