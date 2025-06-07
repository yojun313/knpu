from fastapi import APIRouter, Query, Header, UploadFile, File, Body, Form
from fastapi.responses import StreamingResponse
from app.services.analysis_service import *
from app.models.analysis_model import KemKimOption
import pandas as pd
from io import StringIO
import json
import io, os
from urllib.parse import quote  # 한글 파일명 안전 처리용


router = APIRouter()


@router.post("/kemkim")
async def analysis_kemkim(
    option: str = Form(...),
    token_file: UploadFile = File(...)
):
    option = json.loads(option)
    content = await token_file.read()
    token_data = pd.read_csv(StringIO(content.decode("utf-8")))
    return start_kemkim(KemKimOption(**option), token_data)

@router.post("/tokenize")
async def tokenize_file(
    option: str = Form(...),
    csv_file: UploadFile = File(...)
):

    # ── 요청 파싱 ────────────────────────────────────────────
    option      = json.loads(option)
    content     = await csv_file.read()
    csv_data    = pd.read_csv(io.StringIO(content.decode("utf-8")))

    # ── 토큰화 실행 ──────────────────────────────────────────
    result_df = tokenization(
        pid            = option["pid"],
        data           = csv_data,
        columns        = option["column_names"],
        processes      = None,
        chunksize      = 1_000,
        update_interval = 500,
    )

    # ── DataFrame → CSV(bytes) ──────────────────────────────
    #   • utf-8-sig(Excel 호환) 인코딩
    str_buffer = io.StringIO()
    result_df.to_csv(str_buffer, index=False, encoding="utf-8-sig")
    str_buffer.seek(0)
    byte_buffer = io.BytesIO(str_buffer.read().encode("utf-8-sig"))
    byte_buffer.seek(0)

    filename   = f'token_{os.path.splitext(option["csvfile_name"])[0]}.csv'
    media_type = "text/csv"
    cd_header  = 'attachment; filename*=UTF-8\'\'{}'.format(quote(filename))

    return StreamingResponse(byte_buffer,
                             media_type=media_type,
                             headers={"Content-Disposition": cd_header})
