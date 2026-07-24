import os
import boto3
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

ACCESS_KEY_ID = os.getenv("ACCESS_KEY_ID")
SECRET_ACCESS_KEY = os.getenv("SECRET_ACCESS_KEY")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")
BUCKET_NAME = os.getenv("MANAGER_BUCKET_NAME")
R2_ENDPOINT = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"
PUBLIC_BASE = os.getenv("R2_MANAGER_PUBLIC_URL")

s3 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=ACCESS_KEY_ID,
    aws_secret_access_key=SECRET_ACCESS_KEY,
    region_name="auto",
)


def list_files() -> list:
    response = s3.list_objects_v2(Bucket=BUCKET_NAME)
    files = []
    for obj in response.get("Contents", []):
        size_mb = obj["Size"] / 1024 / 1024
        created = (obj["LastModified"] + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
        files.append(
            {
                "name": obj["Key"],
                "size": f"{size_mb:.1f} MB",
                "created": created,
            }
        )
    files.sort(key=lambda f: f["created"], reverse=True)
    return files


def download_url(filename: str) -> str:
    return f"{PUBLIC_BASE}/{filename}"
