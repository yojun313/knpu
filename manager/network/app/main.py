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
from system.auth.middleware import AuthMiddleware
from app.db import user_logs_db
from system.notify.discord import notify_discord
from system.logging.user_log import AuditLogMiddleware

app = FastAPI(title="KNPU Network Analyzer")

app.add_middleware(AuthMiddleware)
app.add_middleware(
    AuditLogMiddleware,
    service="network",
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
    print(f"[NETWORK] Exception at {request.url.path}:\n{tb}")
    notify_discord(
        "system_error",
        f"[NETWORK] {request.method} {request.url.path}\n```py\n{tb[-1500:]}\n```",
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
# statistics/kemkim/network가 함께 쓰는 테마 시스템(설정 모달 + glass/neu/mesh 스킨) —
# 세 앱 다 이 한 디렉토리를 그대로 마운트해서 파일을 하나만 관리한다.
SHARED_UI_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "system", "ui")
app.mount(
    "/shared-ui", NoCacheStaticFiles(directory=SHARED_UI_DIR), name="shared-ui"
)

app.include_router(api_router)

print("Network viewer server is running...")
