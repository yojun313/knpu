import json
import os
from io import StringIO

import pandas as pd
from fastapi import APIRouter, File, Form, Request, UploadFile

from app.db import user_logs_db
from app.services.network_service import run_network_analysis
from system.logging.user_log import insert_log

from .project_routes import _uid

router = APIRouter()


@router.post("/graph-network")
async def graph_network(
    request: Request,
    option: str = Form(...),
    file: UploadFile = File(...),
):
    option = json.loads(option)
    content = await file.read()
    df = pd.read_csv(StringIO(content.decode("utf-8")))
    uid = _uid(request)
    project_name = os.path.splitext(file.filename)[0]
    result = run_network_analysis(
        option.get("pid", "network"), df, option, uid=uid, project_name=project_name
    )
    insert_log(
        user_logs_db,
        uid,
        "network.analysis.graph_network_run",
        "network",
        target={"type": "analysis", "id": project_name},
    )
    return result
