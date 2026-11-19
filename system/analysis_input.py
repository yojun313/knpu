"""분석 업로드 라우트 공통 입력 처리 — 옵션 JSON·CSV 파일을 읽고 검증한다.

잘못된 JSON·인코딩·CSV와 너무 큰 파일을 분석 시작 전에 400/413으로 돌려준다.
(예전에는 json.loads/decode/read_csv 예외가 그대로 500 내부 오류로 나갔다.)
"""

import json
from io import BytesIO

import pandas as pd
from fastapi import HTTPException, UploadFile

# 직접 업로드 분석 입력 상한. 이보다 큰 데이터는 크롤링 DB에서 불러오는 경로를 쓴다.
MAX_ANALYSIS_UPLOAD_BYTES = 250 * 1024 * 1024
_CHUNK = 1024 * 1024


def parse_option(raw: str) -> dict:
    try:
        option = json.loads(raw)
    except (TypeError, ValueError):
        raise HTTPException(400, "분석 옵션 형식이 올바르지 않습니다.")
    if not isinstance(option, dict):
        raise HTTPException(400, "분석 옵션 형식이 올바르지 않습니다.")
    return option


async def read_upload(
    file: UploadFile, limit: int = MAX_ANALYSIS_UPLOAD_BYTES
) -> bytes:
    """파일을 조각으로 읽으며 상한을 넘으면 바로 멈춘다(전체를 메모리에 올리기 전에)."""
    buf = bytearray()
    while True:
        chunk = await file.read(_CHUNK)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > limit:
            raise HTTPException(
                413,
                f"파일이 너무 큽니다. {limit // (1024 * 1024)}MB 이하로 업로드해 주시기 바랍니다.",
            )
    return bytes(buf)


def parse_csv(content: bytes) -> pd.DataFrame:
    if not content.strip():
        raise HTTPException(400, "빈 파일입니다. CSV 파일을 확인해 주시기 바랍니다.")
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            400, "UTF-8 CSV 파일만 분석할 수 있습니다. 인코딩을 확인해 주시기 바랍니다."
        )
    try:
        df = pd.read_csv(BytesIO(content), encoding="utf-8-sig")
    except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError) as e:
        raise HTTPException(400, f"CSV 파일을 읽지 못했습니다: {e}")
    if df.empty:
        raise HTTPException(400, "CSV에 데이터 행이 없습니다.")
    return df


async def read_analysis_request(
    option: str, file: UploadFile
) -> tuple[dict, pd.DataFrame]:
    opt = parse_option(option)
    df = parse_csv(await read_upload(file))
    return opt, df
