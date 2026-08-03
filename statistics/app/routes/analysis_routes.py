# app/routes/analysis_routes.py
"""매니저 데스크톱 앱이 직접 호출하는 통계 분석 엔드포인트.

예전에는 매니저 서버(manager/server)가 이 분석을 대신 돌리고, 결과를 이 서비스의
/api/internal/projects/ingest로 다시 밀어 넣었다. 이제 분석 자체가 이 프로세스 안에서
돌기 때문에 매니저 서버를 거칠 필요가 없다 — 인증은 AuthMiddleware가 쿠키(브라우저)와
Bearer 토큰(데스크톱 앱) 둘 다 처리해준다."""

import json
import os
from io import StringIO

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.db import user_logs_db
from app.models.analysis_model import StatisticsOption
from app.services.statistics_service import run_statistics_analysis
from system.logging.user_log import insert_log

from .project_routes import _uid

router = APIRouter()


@router.post("/statistics")
async def analysis_statistics(
    request: Request,
    option: str = Form(...),
    file: UploadFile = File(...),
):
    option = json.loads(option)
    content = await file.read()
    df = pd.read_csv(StringIO(content.decode("utf-8")))
    uid = _uid(request)
    project_name = os.path.splitext(file.filename)[0]
    try:
        result = run_statistics_analysis(
            StatisticsOption(**option), df, uid=uid, project_name=project_name
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    insert_log(
        user_logs_db,
        uid,
        "statistics.analysis.statistics_run",
        "statistics",
        target={"type": "analysis", "id": project_name},
    )
    return result
