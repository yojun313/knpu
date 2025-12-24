import os
import subprocess

def fast_zip(folder_path: str, zip_path: str):
    # 이미 zip 파일이 존재할 경우 삭제
    if os.path.exists(zip_path):
        os.remove(zip_path)

    # zip 명령어 실행
    subprocess.run(
        ["7z", "a", "-tzip", "-mx=1", "-mmt=on", zip_path, "."],
        cwd=folder_path,
        stdout=subprocess.DEVNULL,  # 표준 출력 숨기기
        stderr=subprocess.DEVNULL,  # 에러 출력 숨기기
        check=True
    )