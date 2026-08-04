import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

PUBLIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")
MANUALS_DIR = os.path.join(PUBLIC_DIR, "manuals")

_MANUAL_FILES = {
    "hate_analysis": "manual_hate_analysis.html",
    "whisper": "manual_whisper.html",
    "yolo": "manual_yolo.html",
}


@router.get("/")
def manager_intro_page():
    return FileResponse(os.path.join(PUBLIC_DIR, "manager.html"))


@router.get("/manual/{topic}")
def manual_page(topic: str):
    filename = _MANUAL_FILES.get(topic)
    if not filename:
        raise HTTPException(404, "존재하지 않는 매뉴얼입니다")
    return FileResponse(os.path.join(MANUALS_DIR, filename))
