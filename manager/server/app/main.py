from fastapi import FastAPI, Request
from app.routes import api_router
import gc
import asyncio
from datetime import datetime
from rich.console import Console
from rich.table import Table
from starlette.middleware.base import BaseHTTPMiddleware

console = Console()

# ✅ 주기적으로 GC 실행 + 통계 출력
async def periodic_gc(interval_seconds: int = 60):
    while True:
        await asyncio.sleep(interval_seconds)
        collected = gc.collect()
        stats = gc.get_stats()

        table = Table(title="🧹 Garbage Collector Stats", show_lines=True)
        table.add_column("Generation", justify="center", style="cyan")
        table.add_column("Collected", justify="center", style="green")
        table.add_column("Uncollectable", justify="center", style="red")
        table.add_column("Collections", justify="center", style="yellow")
        table.add_column("Objects", justify="center", style="magenta")

        for i, stat in enumerate(stats):
            table.add_row(
                str(i),
                str(stat["collected"]),
                str(stat["uncollectable"]),
                str(stat["collections"]),
                str(stat["objects"]),
            )

        console.clear()
        console.print(table)

# ✅ 요청 로그 미들웨어
class RichLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.now()
        response = await call_next(request)
        process_time = (datetime.now() - start_time).total_seconds()

        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Method", style="cyan")
        table.add_column("Path", style="green")
        table.add_column("Status", style="bold yellow")
        table.add_column("Time", style="dim")
        table.add_column("IP", style="red")

        table.add_row(
            request.method,
            request.url.path,
            str(response.status_code),
            f"{process_time:.2f}s",
            request.client.host,
        )

        console.print(table)
        return response

# ✅ FastAPI 앱 생성 및 구성
app = FastAPI()
app.add_middleware(RichLoggerMiddleware)

@app.on_event("startup")
async def start_background_gc():
    asyncio.create_task(periodic_gc(60))

app.include_router(api_router, prefix="/api", tags=["API"])
