import os
from pathlib import Path

def get_file_size(file_path: str) -> int:
    path_obj = Path(file_path).resolve()
    
    if not path_obj.exists():
        print(f"파일이 존재하지 않습니다: {path_obj}")
        return 0
        
    return path_obj.stat().st_size

def safe_path(path: str) -> str:
    abs_path = os.path.abspath(path)
    if os.name == 'nt' and not abs_path.startswith("\\\\?\\"):
        abs_path = "\\\\?\\" + abs_path
    return abs_path