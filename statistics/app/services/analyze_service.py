# app/services/analyze_service.py
"""
원본 CSV를 웹에서 바로 업로드해 통계분석을 돌리는 기능. manager/server의
/analysis/statistics 엔드포인트(데스크톱 MANAGER가 쓰는 것과 동일한 파이프라인)를 그대로
호출하고, 결과는 manager/server가 알아서(uid 기반) 이 사용자의 프로젝트로 자동
저장해준다. 진행 상황은 manager.knpu.re.kr/progress(WebSocket)로 그대로 흘러간다.
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
MANAGER_SERVER_API = os.getenv(
    "MANAGER_SERVER_INTERNAL_API", "http://localhost:8000/api"
)
# 진행 상황 등록/전송(progress 서버) 내부 호출 주소
PROGRESS_SERVER_URL = os.getenv("PROGRESS_SERVER_URL", "http://localhost:8080").rstrip(
    "/"
)
# 브라우저가 진행 상황 WebSocket에 붙을 때 쓰는 공개 주소
PROGRESS_PUBLIC_WS_URL = (
    "ws://localhost:8080" if MODE == 0 else "wss://manager.knpu.re.kr/progress"
)
# 크롤러 API 내부 호출 주소 — 같은 호스트이므로 로컬로 직접 호출한다 (CORS 불필요,
# '크롤링 DB에서 선택' 기능에서 이 서버가 사용자 세션 쿠키를 실어 서버 간 호출한다)
CRAWLER_INTERNAL_API = os.getenv("CRAWLER_INTERNAL_API", "http://localhost:3001/api")

# 데스크톱 앱의 StatAnalysisDialog와 동일한 플랫폼별 카테고리 매트릭스
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
    session_token: str,
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

    # manager/server는 업로드된 파일명(확장자 제외)을 그대로 프로젝트 이름으로 쓴다
    # (analysis_routes.py). 사용자가 고른 이름을 반영하기 위해 전송 파일명을 바꿔서 보낸다.
    upload_filename = f"{project_name}.csv" if project_name else filename

    def _run():
        try:
            resp = requests.post(
                f"{MANAGER_SERVER_API}/analysis/statistics",
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
            project_id = resp.headers.get("X-Statistics-Project-Id")
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
