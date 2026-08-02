import os
import sys
import traceback
from urllib.parse import quote

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exception_handlers import http_exception_handler
from app.routes import (
    main_routes,
    log_routes,
    bug_routes,
    crawler_routes,
    user_routes,
    pm2_routes,
    nginx_routes,
    ports_routes,
    claude_usage_routes,
    git_routes,
    version_routes,
    settings_routes,
)
from app.db import user_logs_col
from app.libs.jwt import decode_token
from app.libs.discord_notify import notify_discord
from shared.user_log import AuditLogMiddleware


def _extract_identity(request: Request):
    token = request.cookies.get("session")
    payload = decode_token(token) if token else None
    if not payload:
        return None
    return {
        "uid": payload.get("sub"),
        "name": payload.get("name"),
        "role": payload.get("role"),
    }


app = FastAPI(title="FPEI Dashboard")
app.add_middleware(
    AuditLogMiddleware,
    service="admin",
    collection=user_logs_col,
    identity_extractor=_extract_identity,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = exc.__traceback__
    frames = traceback.extract_tb(tb)

    filtered_frames = [
        f
        for f in frames
        if "site-packages" not in f.filename and "lib/python" not in f.filename
    ]
    if not filtered_frames and frames:
        filtered_frames = [frames[-1]]

    custom_traceback = "".join(traceback.format_list(filtered_frames))
    custom_traceback += f"\n{type(exc).__name__}: {str(exc)}"

    print(f"[ADMIN] Exception at {request.url.path}:\n{traceback.format_exc()}")

    notify_discord(
        "system_error",
        f"[ADMIN] {request.method} {request.url.path}\n```py\n{custom_traceback[-1500:]}\n```",
    )

    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": f"[{type(exc).__name__}] {str(exc)}",
            "path": request.url.path,
        },
    )


# 라우터 등록
app.include_router(main_routes.router)
app.include_router(log_routes.router)
app.include_router(bug_routes.router)
app.include_router(crawler_routes.router)
app.include_router(user_routes.router)
app.include_router(pm2_routes.router)
app.include_router(nginx_routes.router)
app.include_router(ports_routes.router)
app.include_router(claude_usage_routes.router)
app.include_router(git_routes.router)
app.include_router(version_routes.router)
app.include_router(settings_routes.router)


@app.exception_handler(StarletteHTTPException)
async def auth_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 307:
        return RedirectResponse(
            url=f"https://knpu.re.kr/login?redirect={quote(str(request.url))}"
        )

    # 그 외의 에러는 기본 에러 메시지 출력
    return await http_exception_handler(request, exc)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=3004)
