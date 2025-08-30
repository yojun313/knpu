import os

def safe_path(path: str) -> str:
    abs_path = os.path.abspath(path)
    if os.name == 'nt' and not abs_path.startswith("\\\\?\\"):
        abs_path = "\\\\?\\" + abs_path
    return abs_path