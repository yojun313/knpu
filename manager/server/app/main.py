import os
import sys

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from app.routes import api_router
from app.routes.site_routes import router as site_router
from app.db import user_logs_db
from system.auth.middleware import AuthMiddleware
from system.notify.discord import notify_discord
from system.logging.user_log import AuditLogMiddleware
from system.shared_ui import mount_shared_ui
import gc
import asyncio
from datetime import datetime
from rich.console import Console
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
import traceback

console = Console()


def _extract_identity(request: Request):
    return (request.scope.get("state") or {}).get("user")


async def periodic_gc(interval_seconds: int = 60):
    while True:
        await asyncio.sleep(interval_seconds)
        gc.collect()


class RichLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.now()
        response = await call_next(request)

        duration = (datetime.now() - start_time).total_seconds()
        status = response.status_code

        status_str = (
            f"[green]{status}[/green]"
            if 200 <= status < 300
            else f"[red]{status}[/red]"
        )

        log_message = (
            f"[dim]{datetime.now().strftime('%H:%M:%S')}[/dim] "
            f"{status_str} "
            f"[cyan]{request.method}[/cyan] "
            f"[green]{request.url.path}[/green] "
            f"[yellow]{duration:.2f}s[/yellow]"
        )
        console.print(log_message)
        return response


app = FastAPI()


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):

    tb = exc.__traceback__
    frames = traceback.extract_tb(tb)

    filtered_frames = []
    for frame in frames:
        if "site-packages" not in frame.filename and "lib/python" not in frame.filename:
            filtered_frames.append(frame)

    if not filtered_frames and frames:
        filtered_frames = [frames[-1]]

    custom_traceback = "".join(traceback.format_list(filtered_frames))
    custom_traceback += f"\n{type(exc).__name__}: {str(exc)}"

    console.print(
        f"[bold red]Exception at {request.url.path}:[/bold red]\n{traceback.format_exc()}"
    )

    notify_discord(
        "system_error",
        f"[MANAGER-SERVER] {request.method} {request.url.path}\n```py\n{custom_traceback[-1500:]}\n```",
    )

    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": f"[{type(exc).__name__}] {str(exc)}",
            "detail": custom_traceback,  # 이제 필터링된 내용만 클라이언트로 전송됨
            "path": request.url.path,
        },
    )


app.add_middleware(RichLoggerMiddleware)
app.add_middleware(
    AuthMiddleware,
    extra_public_paths=[
        "/",
        "/manual/",
        "/api/format/",
        "/api/ping/",
        "/api/download",
        "/assets/",
        "/shared-ui/",
    ],
)
app.add_middleware(
    AuditLogMiddleware,
    service="manager",
    collection=user_logs_db,
    identity_extractor=_extract_identity,
)


@app.on_event("startup")
async def start_background_tasks():
    asyncio.create_task(periodic_gc(60))


app.include_router(site_router, tags=["Site"])
app.include_router(api_router, prefix="/api", tags=["API"])

_PUBLIC_DIR = os.path.join(os.path.dirname(__file__), "public")
app.mount(
    "/assets", StaticFiles(directory=os.path.join(_PUBLIC_DIR, "assets")), name="assets"
)

# kemkim/network/statistics와 같은 테마 시스템(설정 모달 + glass/neu/mesh 스킨) — GPU 기능
mount_shared_ui(app)
