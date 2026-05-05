# app/routers/upload.py
import os, uuid, boto3, mimetypes
from typing import Literal

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

ACCESS_KEY_ID     = os.getenv("ACCESS_KEY_ID")
SECRET_ACCESS_KEY = os.getenv("SECRET_ACCESS_KEY")
ACCOUNT_ID        = os.getenv("ACCOUNT_ID")
BUCKET_NAME       = os.getenv("HOMEPAGE_BUCKET_NAME")
R2_ENDPOINT       = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"

# -------- boto3 클라이언트 ---------
s3 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=ACCESS_KEY_ID,
    aws_secret_access_key=SECRET_ACCESS_KEY,
    region_name="auto",
)

PUBLIC_BASE = "https://pub-60ca29aab33f424fab345807bd058d56.r2.dev"   # ★ 자신의 퍼블릭 도메인

router = APIRouter()

def _allowed(ext: str) -> bool:
    return ext.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}


@router.post(
    "/",
    summary="R2 이미지 업로드",
    response_description="업로드된 이미지 URL",
)
async def upload_image(
    file: UploadFile = File(...),
    object_name: str = Form("default"),
    folder: Literal["members", "news", "papers", "misc"] = Form("misc")
) -> JSONResponse:
    """
    * `file` : multipart/form-data 로 전송되는 이미지 파일\n
    * `folder` : 버킷 내 폴더 (기본 *misc*) – 필요 시 프론트에서 지정
    """
    # 1) 확장자 및 MIME 검사
    _, ext = os.path.splitext(file.filename)
    if not _allowed(ext):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="지원하지 않는 확장자",
        )
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="image/* 만 허용",
        )  
    
    print("object_name:", object_name)

    # 2) object key 생성 (폴더/uuid.ext)
    if object_name == 'default':
        object_name = f"{folder}/{uuid.uuid4().hex}{ext.lower()}"

    # 3) S3 업로드 (stream)
    try:
        s3.upload_fileobj(
            file.file,           # file-like object
            BUCKET_NAME,
            object_name,
            ExtraArgs={"ContentType": file.content_type},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"R2 업로드 실패: {e}",
        )

    # 4) 퍼블릭 URL 반환
    url = f"{PUBLIC_BASE}/{object_name}"
    return JSONResponse({"url": url})
