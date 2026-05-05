import os
from pathlib import Path


def safe_path(path: str | Path) -> Path:
    if not path:
        return Path(".")

    p = Path(path).absolute()

    if os.name == "nt":
        path_str = str(p)
        if len(path_str) >= 250 and not path_str.startswith("\\\\?\\"):
            if path_str.startswith("\\\\"):
                p = Path("\\\\?\\UNC\\" + path_str[2:])
            else:
                p = Path("\\\\?\\" + path_str)

    return p
