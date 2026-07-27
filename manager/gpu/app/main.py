from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.routes import api_router
from app.libs.discord_notify import notify_discord
import gc
import asyncio
import traceback
from datetime import datetime
from rich.console import Console
from starlette.middleware.base import BaseHTTPMiddleware

console = Console()


# 주기적으로 GC 실행
async def periodic_gc(interval_seconds: int = 60):
    while True:
        await asyncio.sleep(interval_seconds)
        gc.collect()


# 요청 로그 미들웨어 (텍스트 출력)
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

        log_message = (
            f"[dim]{time_str}[/dim] "
            f"{status_str} "
            f"[cyan]{method}[/cyan] "
            f"[green]{path}[/green] "
            f"[yellow]{duration_str}[/yellow]"
        )

        console.print(log_message)
        return response


# FastAPI 앱 구성
app = FastAPI()
app.add_middleware(RichLoggerMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    console.print(f"[bold red]Exception at {request.url.path}:[/bold red]\n{tb}")
    notify_discord(
        "system_error",
        f"[MANAGER-GPU] {request.method} {request.url.path}\n```py\n{tb[-1500:]}\n```",
    )
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": str(exc), "path": request.url.path},
    )


@app.on_event("startup")
async def start_background_tasks():
    asyncio.create_task(periodic_gc(60))


@app.on_event("shutdown")
async def stop_background_tasks():
    pass  # 따로 종료할 작업 없음


app.include_router(api_router, prefix="/gpu", tags=["GPU"])
print("Server is running...")
