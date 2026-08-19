import io
import os
import threading
import uuid

import pandas as pd
import requests
from dotenv import load_dotenv
from fastapi.responses import JSONResponse

load_dotenv()

MODE = int(os.getenv("MODE", 1))

# 진행 상황 등록/전송(progress 서버) 내부 호출 주소 — dev/prod가 같은 서버에서
# 같이 떠 있어도 섞이지 않도록, 같은 host 안에서 자기 MODE의 manager_web 포트로 붙는다
# (ecosystem.prod.config.js / ecosystem.dev.config.js의 manager_web PORT와 맞춰둘 것).
PROGRESS_SERVER_URL = os.getenv(
    "PROGRESS_SERVER_URL", f"http://localhost:{18006 if MODE == 0 else 8006}"
).rstrip("/")
# 브라우저가 진행 상황 WebSocket에 붙을 때 쓰는 공개 주소
PROGRESS_PUBLIC_WS_URL = (
    "wss://dev-manager.knpu.re.kr/progress"
    if MODE == 0
    else "wss://manager.knpu.re.kr/progress"
)
# 크롤러 API 내부 호출 주소 — 같은 호스트이므로 로컬로 직접 호출한다 (CORS 불필요,
# '크롤링 DB에서 선택' 기능에서 이 서버가 사용자 세션 쿠키를 실어 서버 간 호출한다)
CRAWLER_INTERNAL_API = os.getenv(
    "CRAWLER_INTERNAL_API", f"http://localhost:{18011 if MODE == 0 else 8011}/api"
)

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

# 메모리 내 작업 상태 추적: pid -> {"status": "running"|"done"|"error", "project_id": ..., "error": ...}
_jobs: dict[str, dict] = {}


def build_option(overrides: dict) -> dict:
    option = dict(_DEFAULT_OPTION)
    for k, v in (overrides or {}).items():
        if k in option and v is not None and v != "":
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
            json={"title": "네트워크 분석", "process_id": pid},
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

    def _run():
        try:
            from app.services.network_service import run_network_analysis

            df = pd.read_csv(io.StringIO(content.decode("utf-8")))
            result = run_network_analysis(
                pid, df, option, uid=uid, project_name=project_name
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
            project_id = result.headers.get("X-Network-Project-Id")
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
