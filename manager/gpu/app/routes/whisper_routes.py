from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from app.services.whisper_service import transcribe_audio
import tempfile
import os
import json

router = APIRouter()

@router.post("/whisper")
async def whisper_route(
    option: str = Form("{}"),
    file: UploadFile = File(...)
):
    """
    option 예시:
    {
        "language": "ko"
    }
    """

    option_dict = json.loads(option)
    language = option_dict.get("language", "ko")

    # 임시 파일 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(await file.read())
        audio_path = tmp.name

    try:
        result = transcribe_audio(
            audio_path=audio_path,
            language=language
        )
    finally:
        os.remove(audio_path)

    return JSONResponse(result)
