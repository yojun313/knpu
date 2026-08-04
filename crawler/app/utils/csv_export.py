import os
import re
from functools import reduce
from typing import Optional

import pandas as pd

# 이 모듈은 ProcessPoolExecutor(spawn) 워커에서 그대로 임포트되므로 app.db(MongoDB
# 연결) 등 무거운/공유하면 안 되는 상태를 절대 임포트하지 않는다 (fork 환경에서
# 부모 프로세스의 MongoClient 소켓을 자식이 공유하게 되는 문제를 원천적으로 피하기 위함).

_DATE_FILTER_COLUMNS = ["Article Date", "Reply Date", "Rereply Date"]


def replaceDatesInFilename(
    filename: str, new_start_date: str, new_end_date: str
) -> str:
    pattern = r"_(\d{8})_(\d{8})_"
    return re.sub(pattern, f"_{new_start_date}_{new_end_date}_", filename)


def replaceKeywordInFilename(name: str, new_keyword: str) -> str:
    parts = name.split("_")

    if "token" in name:
        parts[2] = f"[{new_keyword}]"  # 키워드만 대괄호 포함 교체
    else:
        parts[1] = f"[{new_keyword}]"  # 키워드만 대괄호 포함 교체
    dbname = "_".join(parts)

    replacements = {
        "\\": "＼",  # U+FF3C
        "/": "／",  # U+FF0F
        ":": "：",  # U+FF1A
        "*": "＊",  # U+FF0A
        "?": "？",  # U+FF1F
        '"': "＂",  # U+FF02
        "<": "＜",  # U+FF1C
        ">": "＞",  # U+FF1E
        "|": "¦",  # U+00A6
    }
    for illegal, safe in replacements.items():
        dbname = dbname.replace(illegal, safe)

    return dbname


def apply_date_filter(
    df: pd.DataFrame,
    date_option: str,
    start_date_formed: Optional[str],
    end_date_formed: Optional[str],
) -> pd.DataFrame:
    """'기간 지정'일 때 Article/Reply/Rereply Date 중 먼저 매칭되는 컬럼 기준으로 필터링."""
    if date_option != "part":
        return df

    for col in _DATE_FILTER_COLUMNS:
        if col in df.columns:
            df = df.copy()
            df[col] = pd.to_datetime(df[col], errors="coerce")
            df = df[(df[col] >= start_date_formed) & (df[col] <= end_date_formed)]
            break

    return df


def apply_word_filter(
    df: pd.DataFrame,
    column: str,
    incl_words: list,
    excl_words: list,
    include_all: bool,
) -> pd.DataFrame:
    """포함/제외 단어 필터. pandas의 벡터화된 str.contains를 사용해 행 단위 파이썬
    루프(.apply(lambda ...))보다 대용량 텍스트에서 훨씬 빠르게 동작한다.

    제외 단어는 AND/OR(include_all) 토글과 무관하게 항상 "하나라도 있으면 제외"로
    동작한다 (제외 단어가 2개 이상이고 OR 모드일 때 "전부 다 있어야 제외"로 반대로
    동작하던 버그가 있었음 — 그 필터를 없앤 것).
    """
    text = df[column].astype(str)

    if incl_words:
        masks = [text.str.contains(w, regex=False, na=False) for w in incl_words]
        combine = (lambda a, b: a & b) if include_all else (lambda a, b: a | b)
        combined = reduce(combine, masks)
        df = df[combined]
        text = text[combined]

    if excl_words:
        masks = [text.str.contains(w, regex=False, na=False) for w in excl_words]
        any_excluded = reduce(lambda a, b: a | b, masks)
        df = df[~any_excluded]

    return df


def process_table_task(
    parquet_path: str,
    save_path: str,
    edited_tableName: str,
    encoding: str,
    date_option: str,
    start_date_formed: Optional[str],
    end_date_formed: Optional[str],
    url_filter: Optional[list],
    stats_variant: Optional[dict],
) -> dict:
    """article/statistics 원본 테이블 처리로 얻은 articleURL/statisticsURL이 이미
    확정된 이후의 테이블(reply, rereply, token_* 등)을 별도 프로세스에서 독립적으로
    읽기→필터링→CSV 저장까지 처리한다. 여러 테이블을 ProcessPoolExecutor로 동시에
    돌려 저장 속도를 높이기 위한 함수라 app.db 등 프로세스 간 공유하면 안 되는
    상태(예: MongoDB 커넥션)에 의존하지 않는다.
    """
    tableDF = pd.read_parquet(parquet_path)
    tableDF = apply_date_filter(
        tableDF, date_option, start_date_formed, end_date_formed
    )

    if url_filter is not None:
        tableDF = tableDF[tableDF["Article URL"].isin(url_filter)]

    row_counts = {}

    if stats_variant is not None:
        filteredDF = tableDF[tableDF["Article URL"].isin(stats_variant["url_filter"])]
        filteredDF.to_csv(
            stats_variant["save_path"],
            index=False,
            encoding=encoding,
            errors="replace",
            header=True,
        )
        row_counts[stats_variant["edited_name"]] = len(filteredDF)

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    tableDF.to_csv(
        save_path, index=False, encoding=encoding, errors="replace", header=True
    )
    row_counts[edited_tableName] = len(tableDF)

    return row_counts
