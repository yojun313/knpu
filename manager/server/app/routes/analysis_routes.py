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
  
router = APIRouter()

load_dotenv()
ANALYZER_EXE_PATH = os.getenv("ANALYZER_EXE_PATH")
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