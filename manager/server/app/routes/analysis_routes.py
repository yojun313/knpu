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
    import io, os, json
    import pandas as pd
    from fastapi.responses import StreamingResponse
    from urllib.parse import quote

    # ── 1) 옵션·CSV 파싱 ──────────────────────────────────────
    option    = json.loads(option)
    content   = await csv_file.read()
    csv_data  = pd.read_csv(io.StringIO(content.decode("utf-8")))

    # ── 2) 토큰화 실행 (단일 프로세스) ─────────────────────────
    result_df = tokenization(
        pid     = option["pid"],
        data    = csv_data,
        columns = option["column_names"],
        update_interval = 500,   # 필요 없으면 제거 가능
    )

    # ── 3) DataFrame → CSV (utf-8-sig) ───────────────────────
    byte_buffer = io.BytesIO()
    result_df.to_csv(byte_buffer, index=False, encoding="utf-8-sig")
    byte_buffer.seek(0)

    # ── 4) 스트리밍 응답 ──────────────────────────────────────
    filename   = f'token_{os.path.splitext(option["csvfile_name"])[0]}.csv'
    media_type = "text/csv"
    cd_header  = f"attachment; filename*=UTF-8''{quote(filename)}"

    return StreamingResponse(
        byte_buffer,
        media_type=media_type,
        headers={"Content-Disposition": cd_header},
    )
