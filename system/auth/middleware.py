import asyncio
import logging
from urllib.parse import quote, urlsplit

from starlette.requests import HTTPConnection, Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocketDisconnect

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

# 열린 웹소켓의 세션을 다시 확인하는 주기(초)
WS_REVALIDATE_SECONDS = 30


class AuthMiddleware:
    def __init__(self, app: ASGIApp, *, extra_public_paths: list[str] | None = None):
        self.app = app
        self.public_paths = PUBLIC_PATHS + (extra_public_paths or [])

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "websocket":
            await self._websocket(scope, receive, send)
            return
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
            or path.endswith("/icon-192.png")
            or path.endswith("/icon-512.png")
            or path.endswith("/manifest.webmanifest")
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

    async def _websocket(self, scope: Scope, receive: Receive, send: Send):
        """웹소켓도 같은 세션으로 인증한다. 브라우저는 웹소켓에 CORS를 적용하지 않으므로
        다른 사이트가 사용자의 쿠키로 연결을 여는 것(CSWSH)도 Origin으로 막는다."""
        conn = HTTPConnection(scope)
        path = conn.url.path
        if any(
            path == p if p == "/" else path.startswith(p) for p in self.public_paths
        ):
            await self.app(scope, receive, send)
            return

        origin = conn.headers.get("origin")
        if origin and urlsplit(origin).netloc != conn.headers.get("host"):
            live = None
        else:
            token = conn.cookies.get("session")
            live = revalidate_session(decode_token(token), user_db) if token else None
        if live:
            scope["state"] = {
                "user": {
                    "uid": live["sub"],
                    "name": live["name"],
                    "role": live.get("role"),
                }
            }
            await self._run_watched(scope, receive, send, token)
            return

        message = await receive()
        if message["type"] == "websocket.connect":
            await send({"type": "websocket.close", "code": 1008})

    async def _run_watched(self, scope: Scope, receive: Receive, send: Send, token):
        """연결이 열려 있는 동안에도 주기적으로 세션을 다시 확인한다. 계정이 삭제·차단되거나
        로그아웃(token_version 변경)되면 이미 열린 웹소켓도 끊는다."""
        lock = asyncio.Lock()
        state = {"accepted": False, "closed": False}

        async def guarded_send(message):
            async with lock:
                if state["closed"]:
                    raise WebSocketDisconnect(code=1008)
                if message["type"] == "websocket.accept":
                    state["accepted"] = True
                elif message["type"] == "websocket.close":
                    state["closed"] = True
                await send(message)

        async def watchdog():
            while True:
                await asyncio.sleep(WS_REVALIDATE_SECONDS)
                live = await asyncio.to_thread(
                    revalidate_session, decode_token(token), user_db
                )
                if live:
                    continue
                async with lock:
                    if not state["closed"]:
                        state["closed"] = True
                        await send({"type": "websocket.close", "code": 1008})
                return

        task = asyncio.create_task(watchdog())
        try:
            await self.app(scope, receive, guarded_send)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
