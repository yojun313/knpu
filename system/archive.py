import os
import zipfile


class UnsafeZipError(ValueError):
    pass


def safe_extract_zip(zf: zipfile.ZipFile, dest_dir: str) -> None:
    dest_root = os.path.realpath(dest_dir)

    for member in zf.infolist():
        member_path = os.path.realpath(os.path.join(dest_root, member.filename))
        if member_path != dest_root and not member_path.startswith(dest_root + os.sep):
            raise UnsafeZipError(
                f"zip 안에 허용되지 않는 경로가 있습니다: {member.filename}"
            )

    zf.extractall(dest_root)
