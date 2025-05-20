import boto3
import os
import re
from dotenv import load_dotenv

load_dotenv()

# === 사용자 설정 ===
ACCESS_KEY_ID = os.getenv('ACCESS_KEY_ID')
SECRET_ACCESS_KEY = os.getenv('SECRET_ACCESS_KEY')
ACCOUNT_ID = os.getenv('ACCOUNT_ID')
BUCKET_NAME = os.getenv('BUCKET_NAME')
LOCAL_FOLDER = "D:/BIGMACLAB/MANAGER/Output"  # 파일이 있는 경로
R2_ENDPOINT = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"

# 버전 문자열을 비교 가능한 튜플로 변환 (예: '2.7.1' → (2, 7, 1))


def parse_version(version_str):
    return tuple(map(int, version_str.split(".")))

# 폴더 내 가장 최신 버전 파일 찾기


def find_latest_version_file():
    version_pattern = re.compile(r"BIGMACLAB_MANAGER_(\d+\.\d+\.\d+)\.exe")
    latest_file = None
    latest_version = (0, 0, 0)

    for filename in os.listdir(LOCAL_FOLDER):
        match = version_pattern.match(filename)
        if match:
            version = match.group(1)
            if parse_version(version) > latest_version:
                latest_version = parse_version(version)
                latest_file = filename

    return latest_file


def upload_file(filename):
    local_path = os.path.join(LOCAL_FOLDER, filename)

    if not os.path.exists(local_path):
        print(f"[❌] 파일을 찾을 수 없습니다: {local_path}")
        return

    session = boto3.session.Session()
    client = session.client(
        's3',
        region_name='auto',
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=ACCESS_KEY_ID,
        aws_secret_access_key=SECRET_ACCESS_KEY,
    )

    try:
        print(f"[⏫] 업로드 중: {filename} → R2 버킷 '{BUCKET_NAME}'")
        client.upload_file(local_path, BUCKET_NAME, filename)
        print(
            f"[✅] 업로드 완료: https://{ACCOUNT_ID}.r2.cloudflarestorage.com/{BUCKET_NAME}/{filename}")
    except Exception as e:
        print(f"[❌] 업로드 실패: {e}")


# 메인 실행
if __name__ == "__main__":
    while True:
        version_input = input("업로드할 버전을 입력하세요: ").strip()

        if version_input.lower() == 'n':
            latest_file = find_latest_version_file()
            if latest_file:
                print(f"[🔍] 최신 버전 파일: {latest_file}")
                upload_file(latest_file)
            else:
                print("[❌] 업로드 가능한 버전 파일을 찾을 수 없습니다.")
        else:
            filename = f"BIGMACLAB_MANAGER_{version_input}.exe"
            upload_file(filename)
