import os
import boto3
from dotenv import load_dotenv

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
