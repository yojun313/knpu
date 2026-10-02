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
    crawl_file = params.pop("_crawl_file", None)
    option = dict(params)
    option["pid"] = ctx.id

    input_path, input_filename = ctx.input_path, ctx.input_filename
    if crawl_file:
        # 크롤링 DB에서 고른 경우: 선택 시점에 복사하지 않고 여기서 변환한다.
        input_path, input_filename = _materialize_crawl_input(ctx, crawl_file)

    # tokenfile_name은 kemkim 내부 폴더명 생성("token_" 접두어 제거)에 쓰이므로 실제
    # 업로드된 토큰 CSV 파일명을 그대로 넘긴다.
    option["tokenfile_name"] = input_filename

    ctx.log(f"토큰 파일 읽는 중: {input_filename}")
    token_data = pd.read_csv(input_path, encoding="utf-8")
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


def _materialize_crawl_input(ctx, crawl_file: dict) -> tuple[str, str]:
    """크롤링 DB의 parquet을 이 작업 폴더에 CSV로 풀어 둔다.

    parquet을 row group 단위로 읽어 바로 파일에 쓰므로, 1GB가 넘는 원본이어도
    메모리 사용량이 일정하다.
    """
    from system import crawldata
    from system.jobs import store as job_store
    from system.jobs.errors import JobError

    name = crawl_file.get("name") or ""
    dest = os.path.join(job_store.job_dir(ctx.id), "input.csv")
    ctx.stage("크롤링 데이터 불러오는 중")
    ctx.log(f"크롤링 DB에서 불러오는 중: {name}")
    try:
        written = crawldata.write_csv(crawl_file["uid"], name, dest)
    except crawldata.CrawlDataError as e:
        raise JobError(f"크롤링 데이터를 읽지 못했습니다: {e}")
    ctx.log(f"불러오기 완료 — {written / 1e6:,.1f} MB")
    return dest, crawl_file.get("csv_name") or os.path.basename(dest)
