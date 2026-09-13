import json
import os
import threading
import uuid
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
    "여성/가족", "남성", "성소수자", "인종/국적", "연령",
    "지역", "종교", "기타 혐오", "악플/욕설", "clean",
}

# 메모리 내 작업 상태 추적: pid -> {"status": "running"|"done"|"error", "project_id": ..., "error": ...}
_jobs: dict[str, dict] = {}


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


def _measure_hate_via_gpu(df: pd.DataFrame, pid: str) -> pd.DataFrame:
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

    _send_progress(pid, f"[혐오도 분석] GPU 서버로 전송 중... (총 {len(df):,}행)")

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


def start_job(
    content: bytes,
    filename: str,
    category: str,
    platform: str,
    uid: str,
    project_name: str | None = None,
    extra_options: dict | None = None,
) -> str:
    validate_option(category, platform)

    pid = uuid.uuid4().hex
    _jobs[pid] = {"status": "running", "project_id": None, "error": None}

    try:
        requests.post(
            f"{PROGRESS_SERVER_URL}/process",
            json={"title": "통계 분석", "process_id": pid},
            timeout=10,
        ).raise_for_status()
    except Exception as e:
        _jobs[pid] = {
            "status": "error",
            "project_id": None,
            "error": f"진행 상황 서버 등록 실패: {e}",
        }
        return pid

    option = {"pid": pid, "category": category, "platform": platform}
    if extra_options:
        # 워드클라우드 옵션만 통과시킨다 (임의 필드 주입 방지)
        for key in ("wc_period", "wc_max_words", "wc_exclude"):
            if key in extra_options:
                option[key] = extra_options[key]

    def _run():
        try:
            from app.models.analysis_model import StatisticsOption
            from app.services.statistics_service import run_statistics_analysis

            df = pd.read_csv(StringIO(content.decode("utf-8")))

            # 혐오도 분석: 점수 열이 없는 원본 CSV면 GPU에서 먼저 측정한 뒤
            # 곧바로 통계 분석까지 이어서 진행한다.
            if category == HATE_CATEGORY and _needs_hate_measurement(df):
                df = _measure_hate_via_gpu(df, pid)
                _send_progress(pid, "[혐오도 분석] 측정 완료 — 통계 분석 시작")

            result = run_statistics_analysis(
                StatisticsOption(**option), df, uid=uid, project_name=project_name
            )
            if isinstance(result, JSONResponse):
                import json as _json

                body = _json.loads(bytes(result.body))
                _jobs[pid] = {
                    "status": "error",
                    "project_id": None,
                    "error": body.get("message") or body.get("error") or "분석 실패",
                }
                return
            project_id = result.headers.get("X-Statistics-Project-Id")
            if not project_id:
                _jobs[pid] = {
                    "status": "error",
                    "project_id": None,
                    "error": "분석은 끝났지만 프로젝트로 저장하지 못했습니다.",
                }
                return
            _jobs[pid] = {"status": "done", "project_id": project_id, "error": None}
        except Exception as e:
            _jobs[pid] = {"status": "error", "project_id": None, "error": str(e)}

    threading.Thread(target=_run, daemon=True).start()
    return pid


def get_job(pid: str) -> dict:
    return _jobs.get(pid, {"status": "unknown", "project_id": None, "error": None})
