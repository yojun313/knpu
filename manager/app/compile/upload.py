import os
import re
from dotenv import load_dotenv
from config import (
    SECRET_ACCESS_KEY,
    ACCOUNT_ID,
    BUCKET_NAME,
    OUTPUT_DIRECTORY,
)
import os
import requests

load_dotenv()


def parse_version(version_str):
    return tuple(map(int, version_str.split(".")))


def find_latest_version_file():
    version_pattern = re.compile(r"MANAGER_(\d+\.\d+\.\d+)\.exe")
    latest_file = None
    latest_version = (0, 0, 0)

    for filename in os.listdir(OUTPUT_DIRECTORY):
        match = version_pattern.match(filename)
        if match:
            version = match.group(1)
            if parse_version(version) > latest_version:
                latest_version = parse_version(version)
                latest_file = filename

    return latest_file


def upload_file(local_path):
    filename = os.path.basename(local_path)

    if not os.path.exists(local_path):
        print(f"[❌] 파일을 찾을 수 없습니다: {local_path}")
        return

    url = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com/{BUCKET_NAME}/{filename}"
    headers = {"X-Custom-Auth-Key": SECRET_ACCESS_KEY}

    try:
        print(f"[⏫] 업로드 중: {filename} → R2 버킷 '{BUCKET_NAME}'")
        with open(local_path, "rb") as f:
            response = requests.put(url, headers=headers, data=f)

        if response.status_code == 200:
            print(f"[✅] 업로드 완료: {url}")
        else:
            print(
                f"[❌] 업로드 실패 (상태 코드: {response.status_code}): {response.text}"
            )
    except Exception as e:
        print(f"[❌] 업로드 실패: {e}")


# 메인 실행
if __name__ == "__main__":
    while True:
        version_input = input("업로드할 버전을 입력하세요: ").strip()

        if version_input.lower() == "n":
            latest_file = find_latest_version_file()
            if latest_file:
                print(f"[🔍] 최신 버전 파일: {latest_file}")
                upload_file(latest_file)
            else:
                print("[❌] 업로드 가능한 버전 파일을 찾을 수 없습니다.")
        else:
            filename = f"MANAGER_{version_input}.exe"
            upload_file(filename)
