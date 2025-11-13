from pathlib import Path


def getFolderSize(path):
    total_bytes = sum(f.stat().st_size for f in Path(path).rglob('*') if f.is_file())
    size_gb = total_bytes / (1024 ** 3)
    size_mb = total_bytes / (1024 ** 2)

    # GB, MB 모두 소수점 포함
    size_gb = round(size_gb, 3)   # 예: 0.123 GB
    size_mb = round(size_mb, 2)   # 예: 123.45 MB

    return size_gb, size_mb
