from pathlib import Path


def getFolderSize(path):
    total_bytes = sum(f.stat().st_size for f in Path(path).rglob('*') if f.is_file())
    return total_bytes

def format_size(bytes_size):
    if bytes_size < 1024:  # 1KB 미만
        return f"{bytes_size} B"

    kb = bytes_size / 1024
    if kb < 1024:  # 1MB 미만
        return f"{kb:.2f} KB"

    mb = kb / 1024
    if mb < 1024:  # 1GB 미만
        return f"{mb:.2f} MB"

    gb = mb / 1024
    return f"{gb:.3f} GB"
