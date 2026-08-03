"""zip 압축 해제 안전장치 — kemkim/network/statistics가 사용자 업로드 zip을 풀 때 공용으로 쓴다.

`zipfile.ZipFile.extractall()`은 압축 항목 이름에 있는 `../`나 절대경로를 그대로 믿고
풀어버리므로(zip-slip), 조작된 zip으로 프로젝트 저장 디렉토리 밖에 파일을 쓸 수 있다.
풀기 전에 모든 항목이 대상 디렉토리 안으로만 귀결되는지 먼저 검사하고, 하나라도 벗어나면
아무것도 풀지 않고 예외를 던진다."""

import os
import zipfile


class UnsafeZipError(ValueError):
    pass


def safe_extract_zip(zf: zipfile.ZipFile, dest_dir: str) -> None:
    dest_root = os.path.realpath(dest_dir)

    for member in zf.infolist():
        member_path = os.path.realpath(os.path.join(dest_root, member.filename))
        if member_path != dest_root and not member_path.startswith(
            dest_root + os.sep
        ):
            raise UnsafeZipError(
                f"zip 안에 허용되지 않는 경로가 있습니다: {member.filename}"
            )

    zf.extractall(dest_root)
