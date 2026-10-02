import json
import os

import pandas as pd
from dotenv import load_dotenv
from fastapi.responses import JSONResponse

load_dotenv()

from system.endpoints import (  # noqa: E402
    internal_api,
    internal_url,
    public_ws_url,
)

MANAGER_SERVER_API = os.getenv("MANAGER_SERVER_INTERNAL_API", internal_api("manager"))

PROGRESS_SERVER_URL = os.getenv("PROGRESS_SERVER_URL", internal_url("progress")).rstrip(
    "/"
)

PROGRESS_PUBLIC_WS_URL = public_ws_url("progress")

CRAWLER_INTERNAL_API = os.getenv("CRAWLER_INTERNAL_API", internal_api("crawler"))

_DEFAULT_OPTION = {
    "period": "1y",
    "topword": 500,
    "weight": 0.1,
    "graph_wordcnt": 10,
    "split_option": "평균(Mean)",
    "split_custom": None,
    "filter_option": True,
    "trace_standard": "startyear",
    "ani_option": False,
    "exception_word_list": [],
    "exception_filename": "N",
}


def build_option(overrides: dict) -> dict:
    option = dict(_DEFAULT_OPTION)
    for k, v in (overrides or {}).items():
        if v is not None and v != "":
            option[k] = v
    return option


def run_job(ctx) -> dict:
    """작업 워커 프로세스에서 실행된다(system.jobs.worker). pid = 작업 id."""
    from system.jobs.errors import JobError

    from app.models.analysis_model import KemKimOption
    from app.services.analysis_service import start_kemkim

    params = dict(ctx.params)
    crawl_source = params.pop("_crawl_source", None)
    option = dict(params)
    option["pid"] = ctx.id
    # tokenfile_name은 kemkim 내부 폴더명 생성("token_" 접두어 제거)에 쓰이므로 실제
    # 업로드된 토큰 CSV 파일명을 그대로 넘긴다.
    option["tokenfile_name"] = ctx.input_filename

    ctx.log(f"토큰 파일 읽는 중: {ctx.input_filename}")
    token_data = pd.read_csv(ctx.input_path, encoding="utf-8")
    ctx.log(
        f"데이터 {len(token_data):,}행 · 기간 {option.get('startdate')}~{option.get('enddate')}"
    )
    result = start_kemkim(
        KemKimOption(**option),
        token_data,
        uid=ctx.uid,
        project_name=ctx.title,
        crawl_source=crawl_source,
    )
    if result is None:
        raise JobError(
            "분석이 결과 없이 끝났습니다. 진행 로그의 마지막 메시지를 확인해 주세요."
        )
    if isinstance(result, JSONResponse):
        body = json.loads(bytes(result.body))
        raise JobError(body.get("message") or body.get("error") or "분석 실패")
    project_id = result.headers.get("X-Kemkim-Project-Id")
    if not project_id:
        raise JobError("분석은 끝났지만 프로젝트로 저장하지 못했습니다.")
    return {"project_id": project_id, "summary": f"프로젝트 '{ctx.title}' 생성"}
