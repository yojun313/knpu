# app/routes/analysis_routes.py
"""매니저 데스크톱 앱이 직접 호출하는 KEMKIM 분석 엔드포인트.

예전에는 매니저 서버(manager/server)가 이 분석을 대신 돌리고, 결과를 이 서비스의
/api/internal/projects/ingest로 다시 밀어 넣었다. 이제 분석 자체가 이 프로세스 안에서
돌기 때문에 매니저 서버를 거칠 필요가 없다 — 인증은 AuthMiddleware가 쿠키(브라우저)와
Bearer 토큰(데스크톱 앱) 둘 다 처리해준다."""

import json
import os
from io import StringIO

import pandas as pd
from fastapi import APIRouter, File, Form, Request, UploadFile

from app.db import user_logs_db
from app.models.analysis_model import KemKimOption
from app.services.analysis_service import start_kemkim
from system.logging.user_log import insert_log

from .project_routes import _uid

router = APIRouter()


@router.post("/kemkim")
async def analysis_kemkim(
    request: Request,
    option: str = Form(...),
    file: UploadFile = File(...),
):
    option = json.loads(option)
    content = await file.read()
    token_data = pd.read_csv(StringIO(content.decode("utf-8")))
    uid = _uid(request)
    project_name = os.path.splitext(file.filename)[0]
    result = start_kemkim(
        KemKimOption(**option), token_data, uid=uid, project_name=project_name
    )
    insert_log(
        user_logs_db,
        uid,
        "kemkim.analysis.kemkim_run",
        "kemkim",
        target={"type": "analysis", "id": project_name},
    )
    return result
