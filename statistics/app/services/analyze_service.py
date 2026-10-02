import json
import os
from io import StringIO

import pandas as pd
import requests
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
PROGRESS_PUBLIC_WS_URL = public_ws_url("progress")
CRAWLER_INTERNAL_API = os.getenv("CRAWLER_INTERNAL_API", internal_api("crawler"))
# GPU 서버 (혐오도 측정 + GPU 모니터) — whisper/manager 서버와 동일한 env 키
GPU_SERVER_URL = (os.getenv("GPU_SERVER_URL") or "").rstrip("/")

PLATFORM_CATEGORIES = {
    "Naver News": ["article 분석", "statistics 분석", "reply 분석", "rereply 분석"],
    "Naver Cafe": ["article 분석", "reply 분석"],
    "Google YouTube": ["article 분석", "reply 분석", "rereply 분석"],
}
HATE_CATEGORY = "혐오도 분석"
WORDCLOUD_CATEGORY = "워드클라우드 분석"
COMMON_CATEGORIES = [HATE_CATEGORY, WORDCLOUD_CATEGORY]
# 하위 호환 (예전 프론트가 common_category 단수를 읽음)
COMMON_CATEGORY = HATE_CATEGORY

# GPU 혐오도 측정(option_num=2)이 붙여 주는 레이블 열 — 이 열들이 이미 있으면
# 측정을 건너뛰고 바로 통계 분석으로 넘어간다 (statistics_analysis.HateAnalysis와 동일 기준)
HATE_LABEL_COLS = {
    "여성/가족",
    "남성",
    "성소수자",
    "인종/국적",
    "연령",
    "지역",
    "종교",
    "기타 혐오",
    "악플/욕설",
    "clean",
}


def validate_option(category: str, platform: str) -> None:
    if category in COMMON_CATEGORIES:
        return
    allowed = PLATFORM_CATEGORIES.get(platform)
    if not allowed:
        raise ValueError(f"지원되지 않는 플랫폼입니다: {platform}")
    if category not in allowed:
        raise ValueError(f"{platform}에서는 지원되지 않는 분석입니다: {category}")


def _send_progress(pid: str, text: str) -> None:
    try:
        requests.post(
            f"{PROGRESS_SERVER_URL}/notify/{pid}",
            json={"type": "message", "text": text},
            timeout=10,
        )
    except Exception:
        pass


def _needs_hate_measurement(df: pd.DataFrame) -> bool:
    """이미 혐오도 점수 열이 있으면(매니저 앱 등에서 측정 완료) 재측정하지 않는다."""
    if "Hate" in df.columns:
        return False
    present = [c for c in HATE_LABEL_COLS if c in df.columns]
    return len(present) < 8


def _measure_hate_via_gpu(df: pd.DataFrame, pid: str, log=None) -> pd.DataFrame:
    """GPU 서버의 kor-unsmile 모델로 혐오도 레이블 점수(option_num=2)를 측정해
    점수 열이 붙은 DataFrame을 돌려준다. 진행 메시지는 GPU가 같은 pid로 쏜다."""
    if not GPU_SERVER_URL:
        raise ValueError(
            "서버 설정 오류: GPU_SERVER_URL이 비어 있습니다 (statistics .env 확인)"
        )
    text_col = next((c for c in df.columns if "text" in str(c).lower()), None)
    if text_col is None:
        raise ValueError(
            "혐오도 측정에는 'Text' 열이 필요합니다 (원본 크롤링 CSV를 사용해 주세요)."
        )

    (log or (lambda t: _send_progress(pid, t)))(
        f"[혐오도 분석] GPU 서버로 전송 중... (총 {len(df):,}행)"
    )

    buf = StringIO()
    df.to_csv(buf, index=False)
    option = {"pid": pid, "option_num": 2, "text_col": text_col}
    resp = requests.post(
        f"{GPU_SERVER_URL}/analysis/hate",
        data={"option": json.dumps(option)},
        files={"file": ("data.csv", buf.getvalue().encode("utf-8"), "text/csv")},
        timeout=(30, 3600),
    )
    if resp.status_code != 200:
        raise ValueError(
            f"혐오도 측정 실패 (GPU 서버 {resp.status_code}): {resp.text[:300]}"
        )
    return pd.read_csv(StringIO(resp.content.decode("utf-8")))


def job_kind_label(category: str) -> str:
    return f"통계 분석 · {category}" if category else "통계 분석"


def build_job_params(category: str, platform: str, extra_options: dict | None) -> dict:
    validate_option(category, platform)
    params = {"category": category, "platform": platform}
    if extra_options:
        # 워드클라우드 옵션만 통과시킨다 (임의 필드 주입 방지)
        for key in ("wc_period", "wc_max_words", "wc_exclude"):
            if key in extra_options:
                params[key] = extra_options[key]
    return params


def run_job(ctx) -> dict:
    """작업 워커 프로세스에서 실행된다(system.jobs.worker). pid = 작업 id."""
    from system.jobs.errors import JobError

    from app.models.analysis_model import StatisticsOption
    from app.services.statistics_service import run_statistics_analysis

    pid = ctx.id
    params = dict(ctx.params)
    crawl_file = params.pop("_crawl_file", None)
    category = params.get("category") or ""
    option = {"pid": pid, **params}

    input_path, input_filename = ctx.input_path, ctx.input_filename
    if crawl_file:
        input_path, input_filename = _materialize_crawl_input(ctx, crawl_file)
    ctx.log(f"입력 파일 읽는 중: {input_filename}")
    df = pd.read_csv(input_path, encoding="utf-8")
    ctx.log(f"데이터 {len(df):,}행 · {len(df.columns)}열")

    # 혐오도 분석: 점수 열이 없는 원본 CSV면 GPU에서 먼저 측정한 뒤
    # 곧바로 통계 분석까지 이어서 진행한다.
    if category == HATE_CATEGORY and _needs_hate_measurement(df):
        ctx.stage("GPU 혐오도 측정 중")
        try:
            df = _measure_hate_via_gpu(df, pid, log=ctx.log)
        except ValueError as e:
            raise JobError(str(e))
        ctx.log("[혐오도 분석] 측정 완료 — 통계 분석 시작")

    result = run_statistics_analysis(
        StatisticsOption(**option), df, uid=ctx.uid, project_name=ctx.title
    )
    if result is None:
        raise JobError(
            "분석이 결과 없이 끝났습니다. 진행 로그의 마지막 메시지를 확인해 주세요."
        )
    if isinstance(result, JSONResponse):
        body = json.loads(bytes(result.body))
        raise JobError(body.get("message") or body.get("error") or "분석 실패")
    project_id = result.headers.get("X-Statistics-Project-Id")
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
