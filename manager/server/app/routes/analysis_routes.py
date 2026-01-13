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
from app.libs.exceptions import BadRequestException
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
    async with httpx.AsyncClient(timeout=None) as client:
        # 여러 파일을 같은 필드명("files")으로 반복해서 보내야 FastAPI List[UploadFile]로 받음
        multipart_files = []
        for f in files:
            multipart_files.append(
                ("files", (f.filename, await f.read(), f.content_type))
            )

        data = {
            "option": option,
            "conf_thres": str(conf_thres),  # Form 값은 문자열로 들어오는게 안전
        }

        response = await client.post(
            f"{GPU_SERVER_URL}/analysis/yolo",
            data=data,
            files=multipart_files,
        )

    # GPU 서버가 zip을 스트리밍하든, 에러 json을 보내든 그대로 흘려보냄
    return StreamingResponse(
        response.aiter_bytes(),
        status_code=response.status_code,
        media_type=response.headers.get("content-type", "application/octet-stream"),
        headers={
            # zip 다운로드 유지
            "Content-Disposition": response.headers.get("content-disposition", ""),
        },
    )
    
@router.post("/dino")
async def grounding_dino_proxy_route(
    files: List[UploadFile] = File(...),
    prompt: str = Form(...),
    option: str = Form("{}"),
):
    try:
        option_dict = json.loads(option)
    except json.JSONDecodeError:
        option_dict = {}

    # UploadFile.read()는 한 번 읽으면 포인터 끝이라, 여기서 모두 바이트로 확보
    file_items = []
    for f in files:
        b = await f.read()
        ctype = f.content_type or "application/octet-stream"
        name = f.filename or "image.png"
        # 필드명은 GPU 서버 라우트 파라미터명과 반드시 일치해야 함: files
        file_items.append(("files", (name, b, ctype)))

    try:
        async with httpx.AsyncClient(timeout=None) as client:
            resp = await client.post(
                f"{GPU_SERVER_URL}/analysis/dino",
                data={
                    "prompt": prompt,
                    "option": json.dumps(option_dict, ensure_ascii=False),
                },
                files=file_items,
            )
    except Exception as e:
        raise BadRequestException(
            detail=f"DINO 프록시 요청 실패: {type(e).__name__}: {e}"
        )

    if resp.status_code != 200:
        raise BadRequestException(
            detail=f"DINO 서버 오류 ({resp.status_code}): {resp.text}"
        )

    # GPU 서버가 zip을 내려준다고 가정
    content_type = resp.headers.get("content-type", "application/zip")
    cd = resp.headers.get(
        "content-disposition",
        "attachment; filename*=UTF-8''grounding_dino_results.zip",
    )

    return StreamingResponse(
        io.BytesIO(resp.content),
        media_type=content_type,
        headers={"Content-Disposition": cd},
    )