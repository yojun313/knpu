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
