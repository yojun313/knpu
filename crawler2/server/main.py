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
from app.routes import api_router
import gc
import asyncio
from datetime import datetime
from rich.console import Console
from starlette.middleware.base import BaseHTTPMiddleware
import traceback

console = Console()


# ── 백그라운드 GC ────────────────────────────────────────────────────
async def periodic_gc(interval_seconds: int = 60):
    while True:
        await asyncio.sleep(interval_seconds)
        gc.collect()


# ── 로깅 미들웨어 ────────────────────────────────────────────────────
class RichLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.now()
        response = await call_next(request)
        duration = (datetime.now() - start_time).total_seconds()
        status = response.status_code

        status_str = f"[green]{status}[/green]" if 200 <= status < 300 else f"[red]{status}[/red]"
        log_message = (
            f"[dim]{datetime.now().strftime('%H:%M:%S')}[/dim] "
            f"{status_str} "
            f"[cyan]{request.method}[/cyan] "
            f"[green]{request.url.path}[/green] "
            f"[yellow]{duration:.2f}s[/yellow]"
        )
        console.print(log_message)
        return response


# ── FastAPI 앱 ────────────────────────────────────────────────────────
app = FastAPI(title="Crawler Execution Server", version="0.1.0")


# ── 전역 예외 핸들러 ─────────────────────────────────────────────────
@app.exception_handler(Exception)
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


app.add_middleware(RichLoggerMiddleware)


# ── Startup ──────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    #asyncio.create_task(periodic_gc(60))
    console.print("[bold green]Crawler Execution Server started on port 3005[/bold green]")


# ── 라우터 등록 ──────────────────────────────────────────────────────
app.include_router(api_router, prefix="/api", tags=["API"])
