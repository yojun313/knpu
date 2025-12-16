from fastapi import FastAPI, Request
from app.routes import api_router
from starlette.middleware.base import BaseHTTPMiddleware

import asyncio
import gc
from datetime import datetime

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.text import Text

console = Console()

layout = Layout()
layout.split_column(
    Layout(name="header", size=3),
    Layout(name="logs", ratio=3),
    Layout(name="footer", size=5),
)

log_lines: list[str] = []
MAX_LOGS = 100

# Background Tasks
async def periodic_gc(interval: int = 60):
    while True:
        await asyncio.sleep(interval)
        collected = gc.collect()
        layout["footer"].update(
            Panel(
                f"Last GC: {datetime.now().strftime('%H:%M:%S')}\nCollected objects: {collected}",
                title="SYSTEM",
                border_style="blue",
            )
        )

async def live_ui_loop():
    with Live(layout, console=console, refresh_per_second=4, screen=True):
        while True:
            await asyncio.sleep(0.25)

# Middleware
class RichLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.now()
        response = await call_next(request)
        duration = (datetime.now() - start_time).total_seconds()

        status = response.status_code
        method = request.method
        path = request.url.path

        if 200 <= status < 300:
            status_style = "green"
        elif 300 <= status < 400:
            status_style = "yellow"
        else:
            status_style = "red"

        log_line = (
            f"[dim]{start_time.strftime('%H:%M:%S')}[/dim] "
            f"[{status_style}]{status}[/{status_style}] "
            f"[cyan]{method}[/cyan] "
            f"{path} "
            f"[yellow]{duration:.2f}s[/yellow]"
        )

        log_lines.append(log_line)
        if len(log_lines) > MAX_LOGS:
            log_lines.pop(0)

        layout["logs"].update(
            Panel(
                "\n".join(log_lines),
                title="REQUEST LOGS",
                border_style="cyan",
            )
        )

        return response

# FastAPI App
app = FastAPI()
app.add_middleware(RichLoggerMiddleware)
app.include_router(api_router, prefix="/api", tags=["API"])

@app.on_event("startup")
async def on_startup():
    layout["header"].update(
        Panel(
            Text(
                f"FastAPI server started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                style="bold green",
            ),
            title="SERVER",
            border_style="green",
        )
    )

    layout["logs"].update(
        Panel(
            "Waiting for requests...",
            title="REQUEST LOGS",
            border_style="cyan",
        )
    )

    layout["footer"].update(
        Panel(
            "GC idle",
            title="SYSTEM",
            border_style="blue",
        )
    )

    asyncio.create_task(live_ui_loop())
    asyncio.create_task(periodic_gc(60))
