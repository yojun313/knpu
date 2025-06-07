from fastapi import APIRouter, Query, Header, UploadFile, File, Body, Form
from fastapi.responses import StreamingResponse
from app.services.analysis_service import *
from app.models.analysis_model import KemKimOption
import pandas as pd
from io import StringIO
import json
import io, os, tempfile

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
    option = json.loads(option)
    content = await csv_file.read()
    csv_data = pd.read_csv(StringIO(content.decode("utf-8")))
    
    result_df = tokenization(
        pid           = option.pid,
        data          = csv_data,
        columns       = option.column_names,
        processes     = None,      # mp.cpu_count()
        chunksize     = 1_000,
        update_interval = 500,
    )
    
    buffer = io.BytesIO()
    result_df.to_parquet(buffer, index=False, engine="pyarrow")
    buffer.seek(0)

    filename   = "token_" + os.path.splitext(option.csvfile_name)[0] + ".parquet"
    media_type = "application/x-parquet"

    # ── 4) 스트리밍 응답 생성 ─────────────────────────────────
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"'
    }
    return StreamingResponse(buffer, media_type=media_type, headers=headers)
