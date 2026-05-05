import boto3
import os
from dotenv import load_dotenv

load_dotenv()

# === 사용자 설정 ===
ACCESS_KEY_ID = os.getenv('ACCESS_KEY_ID')
SECRET_ACCESS_KEY = os.getenv('SECRET_ACCESS_KEY')
ACCOUNT_ID = os.getenv('ACCOUNT_ID')
BUCKET_NAME = os.getenv('BUCKET_NAME')
LOCAL_FOLDER = "D:/PAILAB/MANAGER/Output"
R2_ENDPOINT = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"

# S3 클라이언트 생성
s3 = boto3.client(
    's3',
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=ACCESS_KEY_ID,
    aws_secret_access_key=SECRET_ACCESS_KEY,
    region_name='auto'  # R2의 경우 region을 auto로 지정
)


def upload_image(filename: str) -> str:
    """
    이미지를 업로드하고, 업로드된 이미지의 URL 반환
    :param filename: LOCAL_FOLDER 내부 파일 이름 (예: "image.png")
    :return: 업로드된 파일의 퍼블릭 URL
    """
    file_path = os.path.join(LOCAL_FOLDER, filename)
    # 업로드
    s3.upload_file(file_path, BUCKET_NAME, filename)
    # URL 반환
    return get_image_url(filename)


def get_image_url(filename: str) -> str:
    """
    업로드된 파일의 퍼블릭 URL 반환
    :param filename: 업로드된 파일 이름
    """
    return f"{R2_ENDPOINT}/{BUCKET_NAME}/{filename}"


# === 사용 예제 ===
if __name__ == "__main__":
    image_name = "example.png"
    url = upload_image(image_name)
    print(f"업로드 완료, URL: {url}")
