from fastapi import FastAPI, Request
from app.routes import api_router
import gc
import asyncio
from datetime import datetime
from rich.console import Console
from rich.text import Text
from starlette.middleware.base import BaseHTTPMiddleware

console = Console()

# ✅ 주기적으로 GC 수집 및 통계 출력
async def periodic_gc(interval_seconds: int = 60):
    while True:
        await asyncio.sleep(interval_seconds)
        collected = gc.collect()
        stats = gc.get_stats()

        table_text = Text("🧹 GC Stats | ", style="bold green")
        for i, stat in enumerate(stats):
            gen = f"G{i}: "
            table_text.append(f"{gen}", style="cyan")
            table_text.append(f"{stat['collected']} collected, ", style="green")
            table_text.append(f"{stat['uncollectable']} uncollectable", style="red")

            if "objects" in stat:
                table_text.append(f", {stat['objects']} objects", style="magenta")
            table_text.append(" | ")

        console.log(table_text)

# ✅ 깔끔한 요청 로그 미들웨어
class RichLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.now()
        response = await call_next(request)
        duration = (datetime.now() - start_time).total_seconds()

        method = request.method
        path = request.url.path
        status = response.status_code
        client_ip = request.client.host
        time_str = f"{duration:.2f}s"

        status_style = "green"
        if 300 <= status < 400:
            status_style = "yellow"
        elif status >= 400:
            status_style = "red"

        log_text = Text()
        log_text.append(f"[{status}] ", style=status_style)
        log_text.append(f"{method} ", style="bold cyan")
        log_text.append(f"{path} ", style="bold green")
        log_text.append(f"in {time_str} ", style="dim")
        log_text.append(f"from {client_ip}", style="magenta")

        console.log(log_text)
        return response

# ✅ FastAPI 앱 구성
app = FastAPI()
app.add_middleware(RichLoggerMiddleware)

@app.on_event("startup")
async def start_background_gc():
    asyncio.create_task(periodic_gc(60))

app.include_router(api_router, prefix="/api", tags=["API"])
