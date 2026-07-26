import os
import uuid
import boto3
from dotenv import load_dotenv
from fastapi import HTTPException, UploadFile

load_dotenv()

ACCESS_KEY_ID = os.getenv("ACCESS_KEY_ID")
SECRET_ACCESS_KEY = os.getenv("SECRET_ACCESS_KEY")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")
BUCKET_NAME = os.getenv("HOMEPAGE_BUCKET_NAME")
R2_ENDPOINT = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"
PUBLIC_BASE = os.getenv("HOMEPAGE_R2_PUBLIC_URL")

s3 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=ACCESS_KEY_ID,
    aws_secret_access_key=SECRET_ACCESS_KEY,
    region_name="auto",
)


def _allowed(ext: str) -> bool:
    return ext.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def object_name_from_url(url: str) -> str:
    if url.startswith("http"):
        return url.split(f"{PUBLIC_BASE}/")[-1]
    return url


def upload_fileobj(file: UploadFile, folder: str, object_name: str | None = None) -> str:
    _, ext = os.path.splitext(file.filename)
    if not _allowed(ext):
        raise HTTPException(status_code=415, detail="지원하지 않는 확장자")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=415, detail="image/* 만 허용")
    if not object_name:
        object_name = f"{folder}/{uuid.uuid4().hex}{ext.lower()}"
    try:
        s3.upload_fileobj(
            file.file, BUCKET_NAME, object_name, ExtraArgs={"ContentType": file.content_type}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"R2 업로드 실패: {e}")
    return f"{PUBLIC_BASE}/{object_name}"


def delete_object(url_or_object_name: str) -> None:
    s3.delete_object(Bucket=BUCKET_NAME, Key=object_name_from_url(url_or_object_name))
