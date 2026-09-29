import os
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter()


@router.get("/api/me")
def current_user(request: Request):
    user = request.scope.get("state", {}).get("user")
    if not user:
        raise HTTPException(401, "인증이 필요합니다")
    return JSONResponse(user)


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
