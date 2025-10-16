import os
import sys

def get_user_data_dir(app_name: str):
    """운영체제별 표준 사용자 데이터 경로 반환 (appdirs 대체)"""
    home = os.path.expanduser("~")

    if sys.platform.startswith("win"):
        # Windows
        base_dir = os.getenv("LOCALAPPDATA", os.path.join(home, "AppData", "Local"))
    elif sys.platform == "darwin":
        # macOS
        base_dir = os.path.join(home, "Library", "Application Support")
    else:
        # Linux or 기타
        base_dir = os.path.join(home, ".local", "share")

    return os.path.join(base_dir, app_name)

# pandasgui용 로컬 데이터 경로
LOCAL_DATA_DIR = get_user_data_dir("pandasgui")
LOCAL_DATASET_DIR = os.path.join(LOCAL_DATA_DIR, "dataset_files")

os.makedirs(LOCAL_DATA_DIR, exist_ok=True)
os.makedirs(LOCAL_DATASET_DIR, exist_ok=True)

image_path = os.path.join(os.path.dirname(__file__), 'resources', 'images')

PANDASGUI_ICON_PATH = os.path.join(image_path, 'icon.png')
PANDASGUI_ICON_PATH_ICO = os.path.join(image_path, 'icon.ico')

if sys.platform == "win32":
    SHORTCUT_PATH = os.path.join(os.getenv('APPDATA'), 'Microsoft/Windows/Start Menu/Programs/PandasGUI.lnk', )
    PY_INTERPRETTER_PATH = os.path.join(os.path.dirname(sys.executable), 'python.exe')
    PYW_INTERPRETTER_PATH = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')