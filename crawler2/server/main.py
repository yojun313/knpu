import sys
import os

# server/ 디렉토리를 sys.path에 추가 (from app.* 임포트를 위해)
SERVER_DIR = os.path.dirname(__file__)
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

# 크롤러 앱 모듈 경로 등록 (parsers, common, db, config 임포트를 위해)
CRAWLER_APP_PATH = os.path.join(SERVER_DIR, "app")
if CRAWLER_APP_PATH not in sys.path:
    sys.path.insert(0, CRAWLER_APP_PATH)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.auth.middleware import AuthMiddleware
from app.config import MODE
import gc
import asyncio
from datetime import datetime
from rich.console import Console
import traceback

console = Console()


# ── 백그라운드 GC ────────────────────────────────────────────────────
async def periodic_gc(interval_seconds: int = 60):
    while True:
        await asyncio.sleep(interval_seconds)
        gc.collect()


# ── FastAPI 앱 ────────────────────────────────────────────────────────
fastapi_app = FastAPI(title="Crawler Execution Server", version="0.1.0")


# ── CORS ──────────────────────────────────────────────────────────────
cors_origins = ["http://localhost:3005"] if MODE == 0 else [os.getenv("CORS_ORIGIN", "")]
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


# ── 전역 예외 핸들러 ─────────────────────────────────────────────────
@fastapi_app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = exc.__traceback__
    frames = traceback.extract_tb(tb)

    filtered_frames = [
        f for f in frames
        if "site-packages" not in f.filename and "lib/python" not in f.filename
    ]
    if not filtered_frames and frames:
        filtered_frames = [frames[-1]]

    custom_traceback = "".join(traceback.format_list(filtered_frames))
    custom_traceback += f"\n{type(exc).__name__}: {str(exc)}"

    console.print(f"[bold red]Exception at {request.url.path}:[/bold red]\n{traceback.format_exc()}")

    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": f"[{type(exc).__name__}] {str(exc)}",
            "detail": custom_traceback,
            "path": request.url.path,
        },
    )


# ── Startup ──────────────────────────────────────────────────────────
@fastapi_app.on_event("startup")
async def on_startup():
    from app.routes import queue_manager

    # 이전 세션에서 남은 작업 복원
    restore_result = queue_manager.restore_from_db()
    if restore_result["needed"]:
        console.print(
            f"[bold yellow]큐 복원: "
            f"에러 처리 {restore_result['marked_error']}건, "
            f"대기 복원 {restore_result['restored']}건, "
            f"즉시 시작 {restore_result['started']}건[/bold yellow]"
        )
    else:
        console.print("[dim]이전 세션 잔여 작업 없음[/dim]")

    asyncio.create_task(periodic_gc(60))
    console.print("[bold green]Crawler Execution Server started on port 3005[/bold green]")


# ── 정적 파일 ──────────────────────────────────────────────────────
import os as _os
_static_path = _os.path.join(_os.path.dirname(__file__), "app", "static")
fastapi_app.mount("/static", StaticFiles(directory=_static_path), name="static")

# ── 라우터 등록 ──────────────────────────────────────────────────────
from app.routes import api_router
from app.routes.auth_routes import router as auth_router
from app.routes.dashboard_routes import router as dashboard_router
fastapi_app.include_router(auth_router, tags=["Auth"])              # /login, /auth/*
fastapi_app.include_router(dashboard_router, tags=["Dashboard"])    # /
fastapi_app.include_router(api_router, prefix="/api", tags=["API"])


# ── 순수 ASGI 미들웨어 래핑 ──────────────────────────────────────────
# uvicorn이 참조하는 최종 app 객체
# 실행 순서: Auth → FastAPI(CORS → 라우터)
app = AuthMiddleware(fastapi_app)
