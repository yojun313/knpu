import os

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.db import user_logs_db
from app.services.analyze_service import build_option
from app.services.network_service import run_network_analysis
from system.analysis_input import read_analysis_request
from system.logging.user_log import insert_log

from .project_routes import _uid

router = APIRouter()


@router.post("/graph-network")
async def graph_network(
    request: Request,
    option: str = Form(...),
    file: UploadFile = File(...),
):
    raw, df = await read_analysis_request(option, file)
    pid = raw.get("pid", "network")
    # 빠진 키는 기본값으로 채운다(작업 대기열 경로와 동일) — 예전엔 KeyError 500
    option = build_option(raw)
    if not option.get("text_col"):
        raise HTTPException(400, "분석할 텍스트 열(text_col)을 지정해 주시기 바랍니다.")
    uid = _uid(request)
    project_name = os.path.splitext(file.filename or "")[0]
    result = run_network_analysis(pid, df, option, uid=uid, project_name=project_name)
    # 분석이 오류 응답(4xx/5xx)으로 끝났으면 실행 기록을 남기지 않는다
    if getattr(result, "status_code", 200) >= 400:
        return result
    insert_log(
        user_logs_db,
        uid,
        "network.analysis.graph_network_run",
        "network",
        target={"type": "analysis", "id": project_name, "name": project_name},
    )
    return result
