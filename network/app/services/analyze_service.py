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

PROGRESS_SERVER_URL = os.getenv("PROGRESS_SERVER_URL", internal_url("progress")).rstrip(
    "/"
)
# 브라우저가 진행 상황 WebSocket에 붙을 때 쓰는 공개 주소
PROGRESS_PUBLIC_WS_URL = public_ws_url("progress")

CRAWLER_INTERNAL_API = os.getenv("CRAWLER_INTERNAL_API", internal_api("crawler"))

_DEFAULT_OPTION = {
    "text_col": "",
    "scope": "document",
    "window": 4,
    "measure": "raw",
    "period": "total",
    "min_freq": 5,
    "min_edge_weight": 2,
    "top_n": 300,
    "node_size_by": "freq",
    "label_top": 40,
    "centralities": ["degree", "betweenness", "pagerank"],
    "community": "louvain",
    "layout": "fr",
    "backbone": False,
    "backbone_alpha": 0.05,
    "node_color_by": "community",
    "draw_hull": True,
    "adjust_labels": False,
    "compute_kcore": True,
    "compute_structural_holes": True,
    "ego_top": 5,
}


def build_option(overrides: dict) -> dict:
    option = dict(_DEFAULT_OPTION)
    for k, v in (overrides or {}).items():
        if k in option and v is not None and v != "":
            option[k] = v
    return option


def run_job(ctx) -> dict:
    """작업 워커 프로세스에서 실행된다(system.jobs.worker). pid = 작업 id."""
    from system.jobs.errors import JobError

    from app.services.network_service import run_network_analysis

    option = dict(ctx.params)
    crawl_file = option.pop("_crawl_file", None)
    option["pid"] = ctx.id
    input_path, input_filename = ctx.input_path, ctx.input_filename
    if crawl_file:
        input_path, input_filename = _materialize_crawl_input(ctx, crawl_file)
    ctx.log(f"입력 파일 읽는 중: {input_filename}")
    df = pd.read_csv(input_path, encoding="utf-8")
    ctx.log(f"데이터 {len(df):,}행 · 대상 열 '{option.get('text_col')}'")
    result = run_network_analysis(
        ctx.id, df, option, uid=ctx.uid, project_name=ctx.title
    )
    if result is None:
        raise JobError(
            "분석이 결과 없이 끝났습니다. 진행 로그의 마지막 메시지를 확인해 주세요."
        )
    if isinstance(result, JSONResponse):
        body = json.loads(bytes(result.body))
        raise JobError(body.get("message") or body.get("error") or "분석 실패")
    project_id = result.headers.get("X-Network-Project-Id")
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
