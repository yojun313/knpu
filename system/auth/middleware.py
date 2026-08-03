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
    """순수 ASGI 미들웨어. BaseHTTPMiddleware의 StreamingResponse hang 문제를 회피.

    쿠키(session) 인증은 브라우저 뷰어용, Bearer 헤더 인증은 매니저 데스크톱 앱이 자신의
    knpu.re.kr 로그인 토큰으로 각 서비스(kemkim/network/statistics)를 매니저 서버를 거치지
    않고 직접 호출할 때 쓴다.

    예전에는 매니저 서버가 분석 완료 직후 X-Internal-Key로 /api/internal/projects/ingest를
    우회 호출했다. 그 엔드포인트가 제거된 뒤로 이 서비스들에는 그 우회를 쓸 곳이 전혀 없어
    (남은 라우트가 전부 독립적으로 세션/Bearer 인증을 요구한다), 잠재적 공격 표면만 남기지
    않도록 우회 로직 자체를 없앴다."""

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
