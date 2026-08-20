import io
import json
import os
import threading
import uuid

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

# 메모리 내 작업 상태 추적: pid -> {"status": "running"|"done"|"error", "project_id": ..., "error": ...}
_jobs: dict[str, dict] = {}


def build_option(overrides: dict) -> dict:
    option = dict(_DEFAULT_OPTION)
    for k, v in (overrides or {}).items():
        if v is not None and v != "":
            option[k] = v
    return option


def start_job(
    content: bytes,
    filename: str,
    option: dict,
    uid: str,
    project_name: str | None = None,
) -> str:
    pid = uuid.uuid4().hex
    _jobs[pid] = {"status": "running", "project_id": None, "error": None}

    try:
        requests.post(
            f"{PROGRESS_SERVER_URL}/process",
            json={"title": "KEMKIM 분석", "process_id": pid},
            timeout=10,
        ).raise_for_status()
    except Exception as e:
        _jobs[pid] = {
            "status": "error",
            "project_id": None,
            "error": f"진행 상황 서버 등록 실패: {e}",
        }
        return pid

    option = dict(option)
    option["pid"] = pid
    # tokenfile_name은 kemkim 내부 폴더명 생성("token_" 접두어 제거)에 쓰이므로 실제
    # 업로드된 토큰 CSV 파일명을 그대로 넘긴다.
    option["tokenfile_name"] = filename

    def _run():
        try:
            from app.models.analysis_model import KemKimOption
            from app.services.analysis_service import start_kemkim

            token_data = pd.read_csv(io.StringIO(content.decode("utf-8")))
            result = start_kemkim(
                KemKimOption(**option), token_data, uid=uid, project_name=project_name
            )
            if isinstance(result, JSONResponse):
                body = json.loads(bytes(result.body))
                _jobs[pid] = {
                    "status": "error",
                    "project_id": None,
                    "error": body.get("message") or body.get("error") or "분석 실패",
                }
                return
            project_id = result.headers.get("X-Kemkim-Project-Id")
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
