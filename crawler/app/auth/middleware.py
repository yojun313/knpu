import os
from dotenv import load_dotenv
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request
from starlette.responses import RedirectResponse, JSONResponse
from auth.jwt import verify_token
import logging

load_dotenv()

logger = logging.getLogger(__name__)

# 인증 없이 접근 가능한 경로
PUBLIC_PATHS = [
    "/login",
    "/auth/",
    "/api/health",
    "/openapi.json",
    "/docs",
    "/redoc",
]

# 매니저 서버 경유 요청 확인용 내부 키
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

class AuthMiddleware:
    """순수 ASGI 미들웨어. BaseHTTPMiddleware의 StreamingResponse hang 문제를 회피."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # WebSocket은 인증 없이 통과 (대시보드 실시간 연결)
        if scope["type"] == "websocket":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        path = request.url.path

        # 공개 경로
        if any(path.startswith(p) for p in PUBLIC_PATHS):
            await self.app(scope, receive, send)
            return

        # 정적 파일
        if path.startswith("/static/"):
            await self.app(scope, receive, send)
            return

        # 매니저 서버 경유: 내부 API 키
        internal_key = request.headers.get("X-Internal-Key")
        if INTERNAL_API_KEY and internal_key == INTERNAL_API_KEY:
            await self.app(scope, receive, send)
            return

        # 외부 요청 → session cookie 검증
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

        # 인증 실패
        if path.startswith("/api/"):
            response = JSONResponse(
                status_code=401,
                content={"detail": "인증이 필요합니다"},
            )
        else:
            response = RedirectResponse(url="/login", status_code=302)

        await response(scope, receive, send)
