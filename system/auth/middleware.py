import logging
from urllib.parse import quote

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from system.auth.jwt import decode_token
from system.auth.session import revalidate_session
from system.db import user_db

logger = logging.getLogger(__name__)

PUBLIC_PATHS = [
    "/api/health",
    "/openapi.json",
    "/docs",
    "/redoc",
]


class AuthMiddleware:
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

        token = request.cookies.get("session")
        if not token:
            authorization = request.headers.get("Authorization")
            if authorization and authorization.startswith("Bearer "):
                token = authorization[len("Bearer ") :]

        if token:
            payload = decode_token(token)
            live = revalidate_session(payload, user_db)
            if live:
                scope["state"] = {
                    "user": {
                        "uid": live["sub"],
                        "name": live["name"],
                        "role": live.get("role"),
                    }
                }
                await self.app(scope, receive, send)
                return

        # 인증 실패 → knpu.re.kr 중앙 로그인으로 이동
        if path.startswith("/api/"):
            response = JSONResponse(
                status_code=401,
                content={"detail": "인증이 필요합니다"},
            )
        else:
            redirect_url = str(request.url)
            response = RedirectResponse(
                url=f"https://knpu.re.kr/login?redirect={quote(redirect_url)}",
                status_code=302,
            )

        await response(scope, receive, send)
