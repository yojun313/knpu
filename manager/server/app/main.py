from fastapi import FastAPI, Request
from app.routes import api_router
import gc
import asyncio
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.live import Live
from starlette.middleware.base import BaseHTTPMiddleware

console = Console()
log_table = Table(show_header=True, header_style="bold magenta")
log_table.add_column("Time", style="dim", width=8)
log_table.add_column("Status", style="bold")
log_table.add_column("Method", style="cyan")
log_table.add_column("Path", style="green")
log_table.add_column("Duration", justify="right", style="yellow")

live = Live(log_table, console=console, refresh_per_second=4, transient=False)

# ✅ 주기적으로 GC 실행
async def periodic_gc(interval_seconds: int = 60):
    while True:
        await asyncio.sleep(interval_seconds)
        gc.collect()

# ✅ 요청 로그 미들웨어 (테이블에 행 추가)
class RichLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.now()
        response = await call_next(request)
        duration = (datetime.now() - start_time).total_seconds()

        method = request.method
        path = request.url.path
        status = response.status_code
        duration_str = f"{duration:.2f}s"
        time_str = start_time.strftime("%H:%M:%S")

        status_str = str(status)
        if 200 <= status < 300:
            status_str = f"[green]{status}[/green]"
        elif 300 <= status < 400:
            status_str = f"[yellow]{status}[/yellow]"
        else:
            status_str = f"[red]{status}[/red]"

        log_table.add_row(time_str, status_str, method, path, duration_str)
        return response

# ✅ FastAPI 앱 구성
app = FastAPI()
app.add_middleware(RichLoggerMiddleware)

@app.on_event("startup")
async def start_background_tasks():
    live.start()
    asyncio.create_task(periodic_gc(60))

@app.on_event("shutdown")
async def stop_live():
    live.stop()

app.include_router(api_router, prefix="/api", tags=["API"])
