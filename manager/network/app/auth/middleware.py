import os
from dotenv import load_dotenv
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request
from starlette.responses import RedirectResponse, JSONResponse
from app.auth.jwt import verify_token
import logging

load_dotenv()

logger = logging.getLogger(__name__)

PUBLIC_PATHS = [
    "/login",
    "/auth/",
    "/api/health",
    "/openapi.json",
    "/docs",
    "/redoc",
]
# 주의: /api/internal/*은 PUBLIC_PATHS에 넣지 않는다 — X-Internal-Key 검사를 반드시 거쳐야 한다.

# 매니저 서버 경유 요청(내부 ingest) 확인용 키
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")


class AuthMiddleware:
    """순수 ASGI 미들웨어. BaseHTTPMiddleware의 StreamingResponse hang 문제를 회피."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        path = request.url.path

        if any(path.startswith(p) for p in PUBLIC_PATHS):
            await self.app(scope, receive, send)
            return

        if path.startswith("/js/") or path.startswith("/css/"):
            await self.app(scope, receive, send)
            return

        # 매니저 서버 경유: 내부 API 키 (세션 쿠키 없이 통과, uid는 요청 바디로 받음)
        internal_key = request.headers.get("X-Internal-Key")
        if INTERNAL_API_KEY and internal_key == INTERNAL_API_KEY:
            await self.app(scope, receive, send)
            return

        token = request.cookies.get("session")

        if token:
            payload = verify_token(token)
            if payload:
                scope["state"] = {
                    "user": {
                        "uid": payload["sub"],
                        "name": payload["name"],
                    }
                }
                await self.app(scope, receive, send)
                return

        if path.startswith("/api/"):
            response = JSONResponse(
                status_code=401,
                content={"detail": "인증이 필요합니다"},
            )
        else:
            next_url = request.url.path
            if request.url.query:
                next_url += f"?{request.url.query}"
            response = RedirectResponse(
                url=f"/login?next={next_url}", status_code=302
            )

        await response(scope, receive, send)
