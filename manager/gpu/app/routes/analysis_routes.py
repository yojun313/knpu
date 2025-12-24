from fastapi import APIRouter, Query, Header, UploadFile, File, Body, Form
from fastapi.responses import StreamingResponse
from app.services.analysis_service import *
from app.models.analysis_model import KemKimOption
import pandas as pd
from io import StringIO
import json
import io, os
from urllib.parse import quote  

router = APIRouter()

load_dotenv()

@router.post("/hate")
async def hate_measure_route(
    option: str = Form(...),
    file: UploadFile = File(...),
):
    # 옵션 파싱 → HateOption + 부가 파라미터(text_col 등)
    option_dict  = json.loads(option)
    hate_option  = HateOption(
        pid        = option_dict["pid"],
        option_num = option_dict["option_num"],
    )
    text_col     = option_dict.get("text_col", "Text")           

    # CSV → DataFrame
    content  = await file.read()
    df       = pd.read_csv(io.StringIO(content.decode("utf-8")))

    # 혐오도 분석
    result_df = measure_hate(
        option         = hate_option,
        data           = df,
        text_col       = text_col,
        update_interval= 1000,     
    )

    # DataFrame → CSV Bytes
    buffer = io.BytesIO()
    result_df.to_csv(buffer, index=False, encoding="utf-8-sig")
    buffer.seek(0)

    # 스트리밍 응답
    filename   = f"hate_result_opt{hate_option.option_num}.csv"
    media_type = "text/csv"
    cd_header  = f"attachment; filename*=UTF-8''{quote(filename)}"

    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={"Content-Disposition": cd_header},
    )