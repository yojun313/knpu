import os
import threading
import uuid
from io import StringIO

import pandas as pd
import requests
from dotenv import load_dotenv
from fastapi.responses import JSONResponse

load_dotenv()

MODE = int(os.getenv("MODE", 1))

PROGRESS_SERVER_URL = os.getenv(
    "PROGRESS_SERVER_URL", f"http://localhost:{18006 if MODE == 0 else 8006}"
).rstrip("/")
PROGRESS_PUBLIC_WS_URL = (
    "wss://dev-manager.knpu.re.kr/progress"
    if MODE == 0
    else "wss://manager.knpu.re.kr/progress"
)
CRAWLER_INTERNAL_API = os.getenv(
    "CRAWLER_INTERNAL_API", f"http://localhost:{18002 if MODE == 0 else 8002}/api"
)

PLATFORM_CATEGORIES = {
    "Naver News": ["article 분석", "statistics 분석", "reply 분석", "rereply 분석"],
    "Naver Cafe": ["article 분석", "reply 분석"],
    "Google YouTube": ["article 분석", "reply 분석", "rereply 분석"],
}
COMMON_CATEGORY = "혐오도 분석"

# 메모리 내 작업 상태 추적: pid -> {"status": "running"|"done"|"error", "project_id": ..., "error": ...}
_jobs: dict[str, dict] = {}


def validate_option(category: str, platform: str) -> None:
    if category == COMMON_CATEGORY:
        return
    allowed = PLATFORM_CATEGORIES.get(platform)
    if not allowed:
        raise ValueError(f"지원되지 않는 플랫폼입니다: {platform}")
    if category not in allowed:
        raise ValueError(f"{platform}에서는 지원되지 않는 분석입니다: {category}")


def start_job(
    content: bytes,
    filename: str,
    category: str,
    platform: str,
    uid: str,
    project_name: str | None = None,
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

    def _run():
        try:
            from app.models.analysis_model import StatisticsOption
            from app.services.statistics_service import run_statistics_analysis

            df = pd.read_csv(StringIO(content.decode("utf-8")))
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
