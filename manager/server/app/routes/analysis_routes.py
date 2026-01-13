from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from app.services.analysis_service import *
from app.models.analysis_model import KemKimOption
import pandas as pd
from io import StringIO
import json
import io, os
from urllib.parse import quote
import httpx
from dotenv import load_dotenv
from typing import List
  
router = APIRouter()

load_dotenv()

GPU_SERVER_URL = os.getenv("GPU_SERVER_URL")

@router.post("/kemkim")
async def analysis_kemkim(
    option: str = Form(...),
    file: UploadFile = File(...)
):
    option = json.loads(option)
    content = await file.read()
    token_data = pd.read_csv(StringIO(content.decode("utf-8")))
    return start_kemkim(KemKimOption(**option), token_data)

@router.post("/tokenize")
async def tokenize_file(
    option: str = Form(...),
    file: UploadFile = File(...)
):
    option    = json.loads(option)
    content   = await file.read()
    csv_data  = pd.read_csv(io.StringIO(content.decode("utf-8")))

    result_df = tokenization(
        pid     = option["pid"],
        data    = csv_data,
        columns = option["column_names"],
        include_words = option["include_words"],
        update_interval = 500,   
    )

    byte_buffer = io.BytesIO()
    result_df.to_csv(byte_buffer, index=False, encoding="utf-8-sig")
    byte_buffer.seek(0)

    filename   = f'tokenized.csv'
    media_type = "text/csv"
    cd_header  = f"attachment; filename*=UTF-8''{quote(filename)}"

    return StreamingResponse(
        byte_buffer,
        media_type=media_type,
        headers={"Content-Disposition": cd_header},
    )

@router.post("/hate")
async def hate_proxy(
    option: str = Form(...),
    file: UploadFile = File(...)
):
    async with httpx.AsyncClient(timeout=None) as client:
        # multipart 그대로 구성
        files = {
            "file": (file.filename, await file.read(), file.content_type)
        }
        data = {
            "option": option
        }

        # GPU 서버로 전달
        response = await client.post(
            f"{GPU_SERVER_URL}/analysis/hate",
            data=data,
            files=files
        )

    # GPU 서버가 StreamingResponse를 주기 때문에 그대로 반환
    return StreamingResponse(
        response.aiter_bytes(),
        media_type=response.headers.get("content-type"),
        headers={
            "Content-Disposition": response.headers.get("content-disposition", "")
        }
    )

@router.post("/whisper")
async def whisper_proxy(
    option: str = Form("{}"),
    file: UploadFile = File(...)
):
    async with httpx.AsyncClient(timeout=None) as client:
        files = {
            "file": (file.filename, await file.read(), file.content_type)
        }

        data = {
            "option": option
        }

        response = await client.post(
            f"{GPU_SERVER_URL}/analysis/whisper",
            data=data,
            files=files
        )

    return StreamingResponse(
        response.aiter_bytes(),
        media_type=response.headers.get("content-type"),
        headers={
            "Content-Disposition": response.headers.get("content-disposition", "")
        }
    )

@router.post("/youtube")
async def youtube_download(option: str = Form(...)):
    option = json.loads(option)
    return await start_youtube_download(option)

@router.post("/yolo")
async def yolo_proxy(
    option: str = Form("{}"),
    conf_thres: float = Form(0.25),
    files: List[UploadFile] = File(...),
):
    timeout = httpx.Timeout(
        connect=None,
        read=None,
        write=None,
        pool=None,
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        multipart_files = []

        for f in files:
            multipart_files.append(
                (
                    "files",
                    (
                        f.filename,
                        f.file,                 
                        f.content_type or "application/octet-stream",
                    ),
                )
            )

        data = {
            "option": option,
            "conf_thres": str(conf_thres),
        }

        response = await client.post(
            f"{GPU_SERVER_URL}/analysis/yolo",
            data=data,
            files=multipart_files,
        )

    return StreamingResponse(
        response.aiter_bytes(),
        status_code=response.status_code,
        media_type=response.headers.get(
            "content-type",
            "application/octet-stream",
        ),
        headers={
            "Content-Disposition": response.headers.get("content-disposition", "")
        },
    )
