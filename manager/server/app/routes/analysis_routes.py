from fastapi import APIRouter, UploadFile, File, Form, Header
from fastapi.responses import StreamingResponse, JSONResponse
from app.services.analysis_service import (
    tokenization,
    start_youtube_download,
)
from app.services.auth_service import get_uid_from_bearer
import pandas as pd
import json
import io, os
from urllib.parse import quote
import httpx
from dotenv import load_dotenv
from typing import List
from app.libs.exceptions import BadRequestException
from app.db import user_logs_db
from system.logging.user_log import insert_log

router = APIRouter()

load_dotenv()

GPU_SERVER_URL = os.getenv("GPU_SERVER_URL")


@router.post("/tokenize")
async def tokenize_file(option: str = Form(...), file: UploadFile = File(...)):
    option = json.loads(option)
    content = await file.read()
    csv_data = pd.read_csv(io.StringIO(content.decode("utf-8")))

    # option["language"] 추가 (기본값 'ko')
    result_df = tokenization(
        pid=option["pid"],
        data=csv_data,
        columns=option["column_names"],
        include_words=option.get("include_words", []),
        language=option.get("language", "ko"),
        update_interval=500,
    )

    byte_buffer = io.BytesIO()
    result_df.to_csv(byte_buffer, index=False, encoding="utf-8-sig")
    byte_buffer.seek(0)

    filename = f"tokenized.csv"
    media_type = "text/csv"
    cd_header = f"attachment; filename*=UTF-8''{quote(filename)}"

    return StreamingResponse(
        byte_buffer,
        media_type=media_type,
        headers={"Content-Disposition": cd_header},
    )


@router.post("/hate")
async def hate_proxy(option: str = Form(...), file: UploadFile = File(...)):
    async with httpx.AsyncClient(timeout=None) as client:
        # multipart 그대로 구성
        files = {"file": (file.filename, await file.read(), file.content_type)}
        data = {"option": option}

        # GPU 서버로 전달
        response = await client.post(
            f"{GPU_SERVER_URL}/analysis/hate", data=data, files=files
        )

    # GPU 서버가 StreamingResponse를 주기 때문에 그대로 반환
    return StreamingResponse(
        response.aiter_bytes(),
        media_type=response.headers.get("content-type"),
        headers={
            "Content-Disposition": response.headers.get("content-disposition", "")
        },
    )


@router.post("/whisper")
async def whisper_proxy(option: str = Form("{}"), file: UploadFile = File(...)):
    async with httpx.AsyncClient(timeout=None) as client:
        files = {"file": (file.filename, await file.read(), file.content_type)}

        data = {"option": option}

        response = await client.post(
            f"{GPU_SERVER_URL}/analysis/whisper", data=data, files=files
        )

    return StreamingResponse(
        response.aiter_bytes(),
        media_type=response.headers.get("content-type"),
        headers={
            "Content-Disposition": response.headers.get("content-disposition", "")
        },
    )


@router.post("/whisper/stream")
async def whisper_stream_proxy(option: str = Form("{}"), file: UploadFile = File(...)):
    """GPU의 /analysis/whisper/stream(NDJSON 진행 이벤트)을 실시간으로 중계한다.
    위의 whisper_proxy는 client.post()가 응답을 전부 받은 뒤에야 흘려보내는 구조라
    실시간 스트리밍이 되지 않는다 — 여기서는 client.stream()으로 열어 청크가
    도착하는 즉시 그대로 내보낸다 (외부 API 사용자용; whisper 웹사이트는
    GPU_SERVER_URL로 직접 붙으므로 이 프록시를 거치지 않는다)."""
    content = await file.read()
    filename = file.filename
    content_type = file.content_type

    async def relay():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{GPU_SERVER_URL}/analysis/whisper/stream",
                data={"option": option},
                files={"file": (filename, content, content_type)},
            ) as response:
                async for chunk in response.aiter_raw():
                    yield chunk

    return StreamingResponse(relay(), media_type="application/x-ndjson")


@router.get("/gpu/stats")
async def gpu_stats_proxy():
    """GPU 서버의 nvidia-smi 실시간 사용량을 그대로 중계한다."""
    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.get(f"{GPU_SERVER_URL}/analysis/gpu/stats")
    try:
        body = response.json()
    except Exception:
        body = {"error": "invalid response", "gpus": []}
    return JSONResponse(status_code=response.status_code, content=body)


@router.post("/whisper/cancel/{job_id}")
async def whisper_cancel_proxy(job_id: str):
    """진행 중인 스트림 전사(job_id = 스트림 요청 option.job_id) 중단을 GPU 서버로 전달한다."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{GPU_SERVER_URL}/analysis/whisper/cancel/{job_id}"
        )
    try:
        body = response.json()
    except Exception:
        body = {"cancelled": False, "job_id": job_id}
    return JSONResponse(status_code=response.status_code, content=body)


@router.post("/youtube")
async def youtube_download(
    option: str = Form(...), authorization: str | None = Header(None)
):
    option = json.loads(option)
    uid = get_uid_from_bearer(authorization)
    result = await start_youtube_download(option)
    insert_log(
        user_logs_db,
        uid,
        "manager.analysis.youtube_download",
        "manager",
        metadata={
            "count": len(option.get("urls", []) or []),
            "format": option.get("format", "mp3"),
            "save_whisper": bool(option.get("save_whisper", False)),
        },
    )
    return result


@router.get("/yolo/models")
async def get_yolo_models_proxy():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # GPU 서버의 모델 리스트 엔드포인트 호출
            response = await client.get(f"{GPU_SERVER_URL}/analysis/yolo/models")

            if response.status_code != 200:
                return JSONResponse(
                    status_code=response.status_code,
                    content={
                        "message": "GPU 서버에서 모델 리스트를 가져오지 못했습니다.",
                        "detail": response.text,
                    },
                )

            return JSONResponse(content=response.json())

        except Exception as e:
            raise BadRequestException(
                detail=f"GPU 서버 연결 실패: {type(e).__name__}: {e}"
            )


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
        resp.aiter_bytes(),
        status_code=resp.status_code,
        media_type=content_type,
        headers={"Content-Disposition": cd},
    )
