import os
from urllib.parse import quote
from dotenv import load_dotenv
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request
from starlette.responses import RedirectResponse, JSONResponse
from auth.jwt import verify_token
from db import user_db
from shared.session_check import revalidate_session
import logging

load_dotenv()

logger = logging.getLogger(__name__)

PUBLIC_PATHS = [
    "/api/health",
    "/openapi.json",
    "/docs",
    "/redoc",
    "/api/proxy/update",
    "/auth/token-login",
]

# 매니저 서버 경유 요청 확인용 내부 키
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")


class AuthMiddleware:
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
