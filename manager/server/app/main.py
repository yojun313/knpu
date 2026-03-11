import warnings
from requests.exceptions import RequestsDependencyWarning
warnings.filterwarnings("ignore", category=RequestsDependencyWarning)

from fastapi import FastAPI, Request
from app.routes import api_router
import gc
import asyncio
from datetime import datetime
from rich.console import Console
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
import traceback

console = Console()

async def periodic_gc(interval_seconds: int = 60):
    while True:
        await asyncio.sleep(interval_seconds)
        gc.collect()

class RichLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.now()
        
        try:
            response = await call_next(request)
        except Exception as exc:
            time_str = datetime.now().strftime("%H:%M:%S")
            console.print(f"[dim]{time_str}[/dim] [red]CRITICAL[/red] [cyan]{request.method}[/cyan] [green]{request.url.path}[/green]")
            console.print(f"[red]{traceback.format_exc()}[/red]")
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": "Internal Server Error"}
            )

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

app = FastAPI()

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    console.print(f"[bold red]Global Exception Caught:[/bold red] {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "서버 내부에서 오류가 발생했습니다.",
            "path": request.url.path
        },
    )

app.add_middleware(RichLoggerMiddleware)

@app.on_event("startup")
async def start_background_tasks():
    asyncio.create_task(periodic_gc(60))

app.include_router(api_router, prefix="/api", tags=["API"])