import asyncio
import json
import logging
import os
import sys
import traceback
from pathlib import Path
from urllib.parse import urlsplit

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
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.libs.discord_notify import notify_discord
from app.routes import api_router
from app.routes.api import prune_locks
from app.services import store

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
from system.llm_activity import register as register_llm_activity

register_llm_activity(app, "complaint")
app.include_router(api_router, prefix="/api")

PUBLIC_DIR = Path(__file__).resolve().parent / "public"

# ── 보안 설정 ─────────────────────────────────────────────────────────────────
ALLOWED_HOSTS = [
    h.strip()
    for h in (
        os.getenv("COMPLAINT_ALLOWED_HOSTS")
        or "complaint.knpu.re.kr,dev.complaint.knpu.re.kr,localhost,127.0.0.1"
    ).split(",")
    if h.strip()
]
MAX_BODY = 256 * 1024  # 가장 큰 요청(문장 고치기)도 이 안에 들어온다
_UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}

CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        # 화면 코드가 style 속성을 쓰므로 인라인 스타일만 허용한다(스크립트는 허용하지 않음)
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        "font-src 'self' data: https://cdn.jsdelivr.net",
        "img-src 'self' data: blob:",
        "connect-src 'self'",
        # PDF 미리보기는 메모리에서 만든 blob 주소로만 연다
        "frame-src 'self' blob:",
        "object-src 'none'",
        "worker-src 'none'",
        "manifest-src 'self'",
        "media-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": (
        "camera=(), microphone=(), geolocation=(), payment=(), usb=(), "
        "interest-cohort=(), browsing-topics=()"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Permitted-Cross-Domain-Policies": "none",
    # 개인정보가 오가는 서비스라 화면·API·정적 파일 모두 브라우저·중간 캐시에 남기지 않는다
    "Cache-Control": "no-store, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


class BodyLimitMiddleware:
    """본문이 MAX_BODY를 넘는 요청을 거절한다(Content-Length 없는 chunked 포함).

    요청 본문이 작아 앱에 넘기기 전에 끝까지 읽어 크기를 확인한 뒤 그대로 다시 흘려준다.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        length = dict(scope["headers"]).get(b"content-length")
        if length is not None and (not length.isdigit() or int(length) > MAX_BODY):
            return await _reject(send, 413, "요청 내용이 너무 큽니다.")
        messages, size = [], 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] != "http.request":
                break
            size += len(message.get("body", b""))
            if size > MAX_BODY:
                return await _reject(send, 413, "요청 내용이 너무 큽니다.")
            if not message.get("more_body"):
                break

        async def replay():
            return messages.pop(0) if messages else await receive()

        await self.app(scope, replay, send)


async def _reject(send, status: int, detail: str):
    body = json.dumps({"detail": detail}, ensure_ascii=False).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                *(
                    (k.lower().encode(), v.encode())
                    for k, v in SECURITY_HEADERS.items()
                ),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def _https(request: Request) -> bool:
    return (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto", "").split(",")[0].strip() == "https"
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    # 다른 사이트에서 사용자의 브라우저를 빌려 보내는 요청(CSRF)을 막는다
    if request.method in _UNSAFE:
        origin = request.headers.get("origin")
        if origin and urlsplit(origin).netloc != request.headers.get("host"):
            response = JSONResponse({"detail": "허용되지 않은 요청입니다."}, 403)
            response.headers.update(SECURITY_HEADERS)
            return response
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    if _https(request):
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains"
        )
        response.headers["Content-Security-Policy"] = (
            CSP + "; upgrade-insecure-requests"
        )
    return response


app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
app.add_middleware(BodyLimitMiddleware)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # 기본 422 응답은 사용자가 보낸 값을 그대로 되돌려 주므로 위치만 알린다
    fields = sorted({".".join(map(str, e.get("loc", ())[1:])) for e in exc.errors()})
    return JSONResponse(
        status_code=422,
        content={"detail": "입력값을 확인해 주시기 바랍니다.", "fields": fields[:20]},
    )


def _safe_traceback(exc: Exception) -> str:
    """오류 위치만 남긴다. 예외 메시지에는 사용자가 입력한 사건 내용이 섞일 수 있다."""
    frames = "".join(traceback.format_list(traceback.extract_tb(exc.__traceback__)))
    return f"{frames}{type(exc).__module__}.{type(exc).__qualname__}"


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = _safe_traceback(exc)
    logging.error(
        "[COMPLAINT] Exception at %s %s:\n%s", request.method, request.url.path, tb
    )
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
            prune_locks()
        except Exception:
            logging.exception("만료 파일 정리 실패")
        await asyncio.sleep(600)


@app.on_event("startup")
async def _startup():
    asyncio.create_task(_purge_loop())


# SPA: 화면 경로는 모두 index.html (해시 라우팅이라 실제로는 "/"만 쓰인다)
@app.get("/", include_in_schema=False)
def index(request: Request):
    headers = {}
    if _https(request):
        # 이전 버전이 브라우저 저장소에 남긴 값(사건 id 등)까지 접속할 때마다 지운다
        headers["Clear-Site-Data"] = '"storage"'
    return FileResponse(PUBLIC_DIR / "index.html", headers=headers)


from system.shared_ui import NoCacheStaticFiles, SHARED_UI_DIR, _services_js
from fastapi.responses import Response


@app.get("/shared-ui/services.js", include_in_schema=False)
def shared_services():
    return Response(
        _services_js(),
        media_type="application/javascript",
        headers={"cache-control": "no-store"},
    )


app.mount("/shared-ui", NoCacheStaticFiles(directory=SHARED_UI_DIR), name="shared-ui")
app.mount("/", StaticFiles(directory=PUBLIC_DIR), name="static")
