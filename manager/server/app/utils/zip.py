import os
import subprocess

def fast_zip(folder_path: str, zip_path: str):
    # 이미 zip 파일이 존재할 경우 삭제
    if os.path.exists(zip_path):
        os.remove(zip_path)

    # zip 명령어 실행
    subprocess.run(
        ["zip", "-r", "-q", zip_path, "."],  # -r: recursive, -q: quiet(로그 안 찍힘)
        cwd=folder_path,
        check=True
    )