import asyncio
import logging
import os
import sys
import traceback
from pathlib import Path

# 공용 모듈(system.*)을 쓰기 위해 저장소 루트를 경로에 추가한다 (kemkim/app/main.py와 동일한 방식).
_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from dotenv import load_dotenv

# 법령 API·보존 기간 등 모듈 import 시점에 읽는 설정이 있으므로 가장 먼저 읽는다
load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.libs.discord_notify import notify_discord
from app.routes import api_router
from app.services import store

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(api_router, prefix="/api")

PUBLIC_DIR = Path(__file__).resolve().parent / "public"


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    print(f"[COMPLAINT] Exception at {request.url.path}:\n{tb}")
    notify_discord(
        "system_error",
        f"[COMPLAINT] {request.method} {request.url.path}\n```py\n{tb[-1500:]}\n```",
    )
    return JSONResponse(
        status_code=500, content={"detail": "서버 오류가 발생했습니다."}
    )


async def _purge_loop():
    while True:
        try:
            removed = await asyncio.to_thread(store.purge_expired)
            if removed:
                logging.info("보존 기간이 지난 파일 %d개 삭제", removed)
        except Exception:
            logging.exception("만료 파일 정리 실패")
        await asyncio.sleep(3600)


@app.on_event("startup")
async def _startup():
    asyncio.create_task(_purge_loop())


# SPA: 화면 경로는 모두 index.html (해시 라우팅이라 실제로는 "/"만 쓰인다)
@app.get("/", include_in_schema=False)
def index():
    return FileResponse(
        PUBLIC_DIR / "index.html", headers={"Cache-Control": "no-cache"}
    )


app.mount("/", StaticFiles(directory=PUBLIC_DIR), name="static")
