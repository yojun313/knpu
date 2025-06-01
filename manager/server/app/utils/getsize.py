from pathlib import Path


def getFolderSize(path):
    total_bytes = sum(f.stat().st_size for f in Path(path).rglob('*') if f.is_file())
    size_gb = round(total_bytes / (1024 ** 3), 1)
    size_mb_int = int(total_bytes / (1024 ** 2))
    return [size_gb, size_mb_int]
