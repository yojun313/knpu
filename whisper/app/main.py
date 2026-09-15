# app/main.py
import os
import sys
import traceback

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.db import user_logs_db
from app.routes import api_router
from app.routes.page_routes import router as page_router
from app.services.transcribe_service import requeue_interrupted
from system.auth.middleware import AuthMiddleware
from system.logging.user_log import AuditLogMiddleware
from system.notify.discord import notify_discord
from system.shared_ui import mount_shared_ui

app = FastAPI(title="KNPU Whisper STT", docs_url=None, redoc_url=None, openapi_url=None)

app.add_middleware(AuthMiddleware)
app.add_middleware(
    AuditLogMiddleware,
    service="whisper",
    collection=user_logs_db,
    identity_extractor=lambda request: (request.scope.get("state") or {}).get("user"),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    print(f"[WHISPER] Exception at {request.url.path}:\n{tb}")
    notify_discord(
        "system_error",
        f"[WHISPER] {request.method} {request.url.path}\n```py\n{tb[-1500:]}\n```",
    )
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": str(exc), "path": request.url.path},
    )


STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

mount_shared_ui(app)

app.include_router(page_router, tags=["Pages"])
app.include_router(api_router)


@app.on_event("startup")
async def on_startup():
    # 서버 재시작으로 끊긴 변환 작업을 자동으로 이어서 돌린다
    requeue_interrupted()


print("Whisper STT server is running...")
