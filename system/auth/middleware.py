import logging
import os
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
# 주의: /api/internal/*은 PUBLIC_PATHS에 넣지 않는다 — X-Internal-Key 검사를 반드시 거쳐야 한다.

# 매니저 서버 경유 요청(내부 ingest) 확인용 키
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")


class AuthMiddleware:
    """순수 ASGI 미들웨어. BaseHTTPMiddleware의 StreamingResponse hang 문제를 회피.

    쿠키(session) 인증은 브라우저 뷰어용, Bearer 헤더 인증은 매니저 데스크톱 앱이 자신의
    knpu.re.kr 로그인 토큰으로 각 서비스(kemkim/network/statistics)를 매니저 서버를 거치지
    않고 직접 호출할 때 쓴다."""

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
        if not token:
            authorization = request.headers.get("Authorization")
            if authorization and authorization.startswith("Bearer "):
                token = authorization[len("Bearer ") :]

        if token:
            payload = decode_token(token)
            # 계정 삭제/거절/비밀번호·권한 변경 이후에도 예전 토큰이 만료 전까지
            # 계속 통하는 걸 막기 위해, 매 요청마다 homepage.users의 현재 상태를
            # 다시 확인한다.
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
