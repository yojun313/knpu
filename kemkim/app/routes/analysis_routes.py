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
