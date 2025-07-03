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
    option    = json.loads(option)
    content   = await csv_file.read()
    csv_data  = pd.read_csv(io.StringIO(content.decode("utf-8")))

    result_df = tokenization(
        pid     = option["pid"],
        data    = csv_data,
        columns = option["column_names"],
        include_words = option["include_words"],
        update_interval = 500,   # 필요 없으면 제거 가능
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
async def hate_measure_route(
    option: str = Form(...),
    csv_file: UploadFile = File(...),
):
    # 1) 옵션 파싱 → HateOption + 부가 파라미터(text_col 등)
    option_dict  = json.loads(option)
    hate_option  = HateOption(
        pid        = option_dict["pid"],
        option_num = option_dict["option_num"],
    )
    text_col     = option_dict.get("text_col", "Text")           # 없으면 기본값

    # 2) CSV → DataFrame
    content  = await csv_file.read()
    df       = pd.read_csv(io.StringIO(content.decode("utf-8")))

    # 3) 혐오도 분석
    result_df = measure_hate(
        option         = hate_option,
        data           = df,
        text_col       = text_col,
        update_interval= 1000,      # 필요 시 조정
    )

    # 4) DataFrame → CSV Bytes
    buffer = io.BytesIO()
    result_df.to_csv(buffer, index=False, encoding="utf-8-sig")
    buffer.seek(0)

    # 5) 스트리밍 응답
    filename   = f"hate_result_opt{hate_option.option_num}.csv"
    media_type = "text/csv"
    cd_header  = f"attachment; filename*=UTF-8''{quote(filename)}"

    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={"Content-Disposition": cd_header},
    )

