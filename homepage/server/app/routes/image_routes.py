# app/routers/upload.py
import os, uuid, boto3, mimetypes
from typing import Literal
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Query
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

ACCESS_KEY_ID = os.getenv("ACCESS_KEY_ID")
SECRET_ACCESS_KEY = os.getenv("SECRET_ACCESS_KEY")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")
BUCKET_NAME = os.getenv("HOMEPAGE_BUCKET_NAME")
R2_ENDPOINT = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"

s3 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=ACCESS_KEY_ID,
    aws_secret_access_key=SECRET_ACCESS_KEY,
    region_name="auto",
)

PUBLIC_BASE = "https://pub-60ca29aab33f424fab345807bd058d56.r2.dev"

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
    folder: Literal["members", "news", "papers", "gallery", "popup", "misc"] = Form("misc"),
) -> JSONResponse:
    """
    * `file` : multipart/form-data 로 전송되는 이미지 파일\n
    * `folder` : 버킷 내 폴더 (기본 *misc*) – 필요 시 프론트에서 지정
    """
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

    if object_name == "default":
        object_name = f"{folder}/{uuid.uuid4().hex}{ext.lower()}"

    try:
        s3.upload_fileobj(
            file.file,
            BUCKET_NAME,
            object_name,
            ExtraArgs={"ContentType": file.content_type},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"R2 업로드 실패: {e}",
        )

    url = f"{PUBLIC_BASE}/{object_name}"
    return JSONResponse({"url": url})


@router.delete(
    "/",
    summary="R2 이미지 삭제",
)
async def delete_image(
    object_name: str = Query(
        ..., description="삭제할 객체의 전체 경로 (예: members/uuid.jpg)"
    ),
) -> JSONResponse:
    try:
        s3.delete_object(
            Bucket=BUCKET_NAME,
            Key=object_name,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"R2 삭제 실패: {e}",
        )

    return JSONResponse({"message": f"Object '{object_name}' deleted successfully"})
