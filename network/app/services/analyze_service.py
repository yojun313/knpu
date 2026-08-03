# app/services/analyze_service.py
"""
토큰화된 CSV를 웹에서 바로 업로드해 네트워크 분석을 돌리는 기능. 데스크톱 MANAGER가
/api/analysis/graph-network로 호출하는 것과 같은 분석 함수(network_service.run_network_analysis)를
이 프로세스 안에서 직접 돌리고, 끝나면 uid 기반으로 이 사용자의 프로젝트로 자동 저장한다.
(예전에는 매니저 서버에 HTTP로 위임하고 매니저 서버가 다시 이 서비스로 결과를 밀어
넣는 왕복 구조였다.) 진행 상황은 manager.knpu.re.kr/progress(WebSocket)로 그대로 흘러간다.
"""

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
