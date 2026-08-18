# app/main.py
import os
import sys
import traceback

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from app.routes import api_router
from app.db import user_logs_db, ensure_indexes
from system.auth.middleware import AuthMiddleware
from system.notify.discord import notify_discord
from system.logging.user_log import AuditLogMiddleware

app = FastAPI(title="KNPU AHP")

app.add_middleware(
    AuthMiddleware,
    extra_public_paths=[
        # 응답자는 익명이라 로그인 없이 접근한다 (PLAN.md 5.2).
        "/r/",
        "/api/respond/",
        # /js/ /css/는 system.auth.middleware가 항상 공개로 취급하지만 /img/는
        # 아니다 — 응답자 페이지가 로고·파비콘을 못 불러오는 조용한 버그가 될
        # 뻔했다(하드코딩된 예외에 /img/가 빠져 있음).
        "/img/",
    ],
)
app.add_middleware(
    AuditLogMiddleware,
    service="ahp",
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
    print(f"[AHP] Exception at {request.url.path}:\n{tb}")
    notify_discord(
        "system_error",
        f"[AHP] {request.method} {request.url.path}\n```py\n{tb[-1500:]}\n```",
    )
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": str(exc), "path": request.url.path},
    )


class NoCacheStaticFiles(StaticFiles):
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

# 관리자 화면 전용 — 테마 시스템(글래스/애플/뉴모피즘/메시 + 다크). 응답자 화면은
# 이 마운트를 아예 참조하지 않는다(PLAN.md 10.2 — 시스템 라이트/다크만, 테마 선택 없음).
SHARED_UI_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "system", "ui")
app.mount("/shared-ui", NoCacheStaticFiles(directory=SHARED_UI_DIR), name="shared-ui")

app.include_router(api_router)


@app.on_event("startup")
async def _startup():
    await ensure_indexes()


print("AHP server is running...")
