import os

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.db import user_logs_db
from app.models.analysis_model import KemKimOption
from app.services.analysis_service import start_kemkim
from system.analysis_input import read_analysis_request
from system.logging.user_log import insert_log

from .project_routes import _uid

router = APIRouter()


@router.post("/kemkim")
async def analysis_kemkim(
    request: Request,
    option: str = Form(...),
    file: UploadFile = File(...),
):
    option, token_data = await read_analysis_request(option, file)
    uid = _uid(request)
    project_name = os.path.splitext(file.filename or "")[0]
    try:
        result = start_kemkim(
            KemKimOption(**option), token_data, uid=uid, project_name=project_name
        )
    except ValueError as e:  # 입력 검증 실패(열 누락·유효 날짜 없음 등)와 옵션 오류
        raise HTTPException(400, str(e))
    if getattr(result, "status_code", 200) >= 400:
        return result
    insert_log(
        user_logs_db,
        uid,
        "kemkim.analysis.kemkim_run",
        "kemkim",
        target={"type": "analysis", "id": project_name, "name": project_name},
    )
    return result
