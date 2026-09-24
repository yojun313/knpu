import logging
from urllib.parse import quote

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from system.auth.jwt import decode_token
from system.auth.session import revalidate_session
from system.db import user_db
from system.endpoints import LOGIN_URL

logger = logging.getLogger(__name__)

# /docs·/redoc·/openapi.json은 모든 앱에서 비활성화되어(main.py의 docs_url=None 등)
# 더 이상 존재하지 않는다 — 공개 경로에서도 제외해 이중으로 막는다.
PUBLIC_PATHS = [
    "/api/health",
]


class AuthMiddleware:
    def __init__(self, app: ASGIApp, *, extra_public_paths: list[str] | None = None):
        self.app = app
        self.public_paths = PUBLIC_PATHS + (extra_public_paths or [])

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        path = request.url.path

        # "/"는 다른 모든 경로의 접두어이기도 하므로 startswith가 아니라 정확히
        # 일치할 때만 공개 경로로 취급한다 (안 그러면 전체 API가 공개된다).
        if any(
            path == p if p == "/" else path.startswith(p) for p in self.public_paths
        ):
            await self.app(scope, receive, send)
            return

        # 정적 자산은 로그인 없이도 받을 수 있어야 한다. /shared-ui 에는 공개
        # 도메인 이름(services.js)과 테마 자산만 들어 있어 감출 것이 없다.
        if (
            path.startswith("/js/")
            or path.startswith("/css/")
            or path.startswith("/shared-ui/")
            # 브라우저/iOS가 쿠키 없이 요청할 수 있는 사이트 아이콘.
            # 302 로그인 리다이렉트를 받으면 iOS 홈화면 아이콘이 스크린샷으로
            # 대체되므로 파일명 단위로 공개한다.
            or path.endswith("/favicon.ico")
            or path.endswith("/apple-touch-icon.png")
        ):
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

        # 인증 실패 → 중앙 로그인으로 이동 (주소는 services.json)
        if path.startswith("/api/"):
            response = JSONResponse(
                status_code=401,
                content={"detail": "인증이 필요합니다"},
            )
        else:
            # request.url은 uvicorn이 프록시 뒤에 있다는 걸 모르기 때문에 scheme이
            # 항상 http로 찍힌다 — nginx가 TLS를 종료하므로 실제로 http로 오는 경우는
            # 없으니 https로 강제한다. 그렇지 않으면 로그인 후 되돌아갈 때 Secure
            # 쿠키가 http 요청에 실리지 않아 리다이렉트가 깨진다.
            redirect_url = str(request.url.replace(scheme="https"))
            response = RedirectResponse(
                url=f"{LOGIN_URL}?redirect={quote(redirect_url)}",
                status_code=302,
            )

        await response(scope, receive, send)
