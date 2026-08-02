# app/main.py
import os
import sys
import traceback

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from app.routes import api_router
from app.auth.middleware import AuthMiddleware
from app.db import user_logs_db
from app.libs.discord_notify import notify_discord
from shared.user_log import AuditLogMiddleware

app = FastAPI(title="KNPU Statistics Analyzer")

app.add_middleware(AuthMiddleware)
app.add_middleware(
    AuditLogMiddleware,
    service="statistics",
    collection=user_logs_db,
    identity_extractor=lambda request: (request.scope.get("state") or {}).get("user"),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    print(f"[STATISTICS] Exception at {request.url.path}:\n{tb}")
    notify_discord(
        "system_error",
        f"[STATISTICS] {request.method} {request.url.path}\n```py\n{tb[-1500:]}\n```",
    )
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": str(exc), "path": request.url.path},
    )


class NoCacheStaticFiles(StaticFiles):
    """개발 중 자산(js/css)이 자주 바뀌므로 브라우저가 캐시된 옛 버전을 계속 쓰는 일이
    없도록 캐시를 끈다. 정적 파일이 몇 개 안 되는 내부 도구라 성능 영향은 무시할 만하다."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"cache-control", b"no-store, must-revalidate"))
                message = {**message, "headers": headers}
            await send(message)

        await super().__call__(scope, receive, send_wrapper)


STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount(
    "/js", NoCacheStaticFiles(directory=os.path.join(STATIC_DIR, "js")), name="js"
)
app.mount(
    "/css", NoCacheStaticFiles(directory=os.path.join(STATIC_DIR, "css")), name="css"
)
app.mount(
    "/img", NoCacheStaticFiles(directory=os.path.join(STATIC_DIR, "img")), name="img"
)

app.include_router(api_router)

print("Statistics viewer server is running...")
