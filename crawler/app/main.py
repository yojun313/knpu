import sys
import os

SERVER_DIR = os.path.dirname(__file__)
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

CRAWLER_APP_PATH = os.path.join(SERVER_DIR, "app")
if CRAWLER_APP_PATH not in sys.path:
    sys.path.insert(0, CRAWLER_APP_PATH)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.auth.middleware import AuthMiddleware
from app.common.audit_log import AuditLogMiddleware
from app.common.notification import sendDiscord
from app.config import MODE
import gc
import asyncio
from datetime import datetime
from rich.console import Console
import traceback

console = Console()


async def periodic_gc(interval_seconds: int = 60):
    while True:
        await asyncio.sleep(interval_seconds)
        gc.collect()


fastapi_app = FastAPI(title="CRAWLER")

cors_origins = ["http://localhost:3001", "https://crawler.knpu.re.kr"]
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


@fastapi_app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = exc.__traceback__
    frames = traceback.extract_tb(tb)

    filtered_frames = [
        f
        for f in frames
        if "site-packages" not in f.filename and "lib/python" not in f.filename
    ]
    if not filtered_frames and frames:
        filtered_frames = [frames[-1]]

    custom_traceback = "".join(traceback.format_list(filtered_frames))
    custom_traceback += f"\n{type(exc).__name__}: {str(exc)}"

    console.print(
        f"[bold red]Exception at {request.url.path}:[/bold red]\n{traceback.format_exc()}"
    )

    sendDiscord(
        f"[CRAWLER] {request.method} {request.url.path}\n```py\n{custom_traceback[-1500:]}\n```",
        "system_error",
    )

    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": f"[{type(exc).__name__}] {str(exc)}",
            "detail": custom_traceback,
            "path": request.url.path,
        },
    )


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
    console.print("[bold green]Crawler Execution Server started[/bold green]")


import os as _os

_static_path = _os.path.join(_os.path.dirname(__file__), "static")
fastapi_app.mount("/static", StaticFiles(directory=_static_path), name="static")

from app.routes import api_router
from app.routes.dashboard_routes import router as dashboard_router

fastapi_app.include_router(dashboard_router, tags=["Dashboard"])
fastapi_app.include_router(api_router, prefix="/api", tags=["API"])

app = AuthMiddleware(AuditLogMiddleware(fastapi_app))
