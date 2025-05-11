from fastapi import APIRouter, Query, Header, UploadFile, File, Body, Form
from app.services.analysis_service import start_kemkim
from app.models.analysis_model import KemKimOption
import pandas as pd
from io import StringIO
import json

router = APIRouter()


@router.post("/kemkim")
async def analysis_kemkim(
    option: str = Form(...),
    token_file: UploadFile = File(...)
):
    option = json.loads(option)
    content = await token_file.read()
    token_data = pd.read_csv(StringIO(content.decode("utf-8")))
    return start_kemkim(KemKimOption(**option), token_data)
