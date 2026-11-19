import os

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.db import user_logs_db
from app.models.analysis_model import StatisticsOption
from app.services.statistics_service import run_statistics_analysis
from system.analysis_input import read_analysis_request
from system.logging.user_log import insert_log

from .project_routes import _uid

router = APIRouter()


@router.post("/statistics")
async def analysis_statistics(
    request: Request,
    option: str = Form(...),
    file: UploadFile = File(...),
):
    option, df = await read_analysis_request(option, file)
    uid = _uid(request)
    project_name = os.path.splitext(file.filename or "")[0]
    try:
        result = run_statistics_analysis(
            StatisticsOption(**option), df, uid=uid, project_name=project_name
        )
    except ValueError as e:  # pydantic ValidationError 포함
        raise HTTPException(400, str(e))
    # 분석이 오류 응답으로 끝났으면 실행 기록을 남기지 않는다
    if getattr(result, "status_code", 200) >= 400:
        return result
    insert_log(
        user_logs_db,
        uid,
        "statistics.analysis.statistics_run",
        "statistics",
        target={"type": "analysis", "id": project_name, "name": project_name},
    )
    return result
