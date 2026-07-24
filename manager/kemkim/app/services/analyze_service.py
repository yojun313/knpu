# app/services/analyze_service.py
"""
토큰화된 CSV를 웹에서 바로 업로드해 KEMKIM 분석을 돌리는 기능.
manager/server의 /analysis/kemkim 엔드포인트(데스크톱 MANAGER가 쓰는 것과 동일한
파이프라인)를 그대로 호출하고, 결과는 manager/server가 알아서(uid 기반) 이 사용자의
프로젝트로 자동 저장해준다. 진행 상황은 manager-progress 서버(WebSocket)로 그대로 흘러간다.
"""

import json
import os
import threading
import uuid

import requests
from dotenv import load_dotenv

load_dotenv()

MODE = int(os.getenv("MODE", 1))

# 매니저 서버(분석 파이프라인) 내부 호출 주소 — 같은 호스트이므로 로컬로 직접 호출한다.
# (공유 .env의 MANAGER_SERVER_URL은 이미 /api가 붙은 공개 프로덕션 주소라 내부 호출에는
# 쓰지 않는다 — network/app/services/analyze_service.py와 동일한 패턴)
MANAGER_SERVER_API = os.getenv(
    "MANAGER_SERVER_INTERNAL_API", "http://localhost:8000/api"
)
# 진행 상황 등록/전송(progress 서버) 내부 호출 주소
PROGRESS_SERVER_URL = os.getenv("PROGRESS_SERVER_URL", "http://localhost:8080").rstrip(
    "/"
)
# 브라우저가 진행 상황 WebSocket에 붙을 때 쓰는 공개 주소
PROGRESS_PUBLIC_WS_URL = (
    "ws://localhost:8080" if MODE == 0 else "wss://manager-progress.knpu.re.kr"
)

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
    session_token: str,
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

    # manager/server는 업로드된 파일명(확장자 제외)을 그대로 프로젝트 이름으로 쓴다
    # (analysis_routes.py). 분석 백엔드 코드를 건드리지 않고 사용자가 고른 이름을
    # 반영하기 위해, 전송하는 파일명 자체를 사용자가 정한 이름으로 바꿔서 보낸다.
    upload_filename = f"{project_name}.csv" if project_name else filename

    def _run():
        try:
            resp = requests.post(
                f"{MANAGER_SERVER_API}/analysis/kemkim",
                headers={"Authorization": f"Bearer {session_token}"},
                data={"option": json.dumps(option)},
                files={"file": (upload_filename, content, "text/csv")},
                timeout=3600,
            )
            if resp.status_code != 200:
                _jobs[pid] = {
                    "status": "error",
                    "project_id": None,
                    "error": f"분석 서버 오류 (HTTP {resp.status_code}): {resp.text[:300]}",
                }
                return
            project_id = resp.headers.get("X-Kemkim-Project-Id")
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
