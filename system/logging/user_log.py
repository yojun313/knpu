import logging
import contextvars
import time
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from starlette.requests import Request
from starlette.routing import Match, Mount
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
KST = ZoneInfo("Asia/Seoul")
_log_client = contextvars.ContextVar("user_log_client", default=None)


def manager_client(scope: Scope) -> str:
    """Classify log origin, including desktop releases predating the client header.

    This is diagnostic metadata, not an authentication or authorization check.
    """
    request = Request(scope)
    if request.headers.get("sec-fetch-mode") or request.cookies.get("session"):
        return "web"
    if request.headers.get("x-knpu-client") == "manager-app":
        return "manager-app"
    if request.headers.get("authorization", "").startswith(
        "Bearer "
    ) and request.headers.get("user-agent", "").lower().startswith("python-requests/"):
        return "manager-app"
    return "web"


class ManagerLogClientMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        token = _log_client.set(manager_client(scope))
        try:
            await self.app(scope, receive, send)
        finally:
            _log_client.reset(token)


def _now_kst():
    now = datetime.now(timezone.utc)
    return now, now.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S")


def build_entry(
    user_uid: Optional[str],
    action: str,
    service: str,
    *,
    message: Optional[str] = None,
    target: Optional[dict] = None,
    outcome: str = "success",
    role: Optional[str] = None,
    request_info: Optional[dict] = None,
    metadata: Optional[dict] = None,
    source: str = "explicit",
) -> dict:
    now_utc, now_kst = _now_kst()

    if message is None:
        if target and target.get("id"):
            message = f"{action}: {target['id']}"
        else:
            message = action

    return {
        "uid": str(uuid.uuid4()),
        "userUid": user_uid,
        "datetime": now_utc,
        "datetime_kst": now_kst,
        "message": message,
        "schema": SCHEMA_VERSION,
        "action": action,
        "service": service,
        "role": role,
        "target": target,
        "outcome": outcome,
        "request": request_info,
        "metadata": metadata or {},
        # "explicit": 비즈니스 로직이 무엇을 했는지 알고 의도적으로 남긴 기록(User Logs 탭).
        # "auto": AuditLogMiddleware가 모든 변경 요청에 대해 자동으로 남긴 기록(Audit Logs 탭).
        "source": source,
    }


def insert_log(
    collection,
    user_uid: Optional[str],
    action: str,
    service: str,
    **kwargs,
) -> None:
    try:
        client = _log_client.get()
        if service == "manager" and client:
            kwargs["metadata"] = {**(kwargs.get("metadata") or {}), "client": client}
            if client == "web":
                board_action = action.startswith(
                    (
                        "manager.version.",
                        "manager.bug.",
                        "manager.post.",
                        "manager.free.",
                        "manager.suggestion.",
                    )
                )
                service = "board" if board_action else "manager_web"
                if action.startswith("manager."):
                    action = service + action[len("manager") :]
        entry = build_entry(user_uid, action, service, **kwargs)
        collection.insert_one(entry)
    except Exception:
        logger.warning(
            "user_log insert 실패 (action=%s, service=%s)",
            action,
            service,
            exc_info=True,
        )


def route_exists(routes, scope: Scope) -> bool:
    """요청의 경로와 메서드를 모두 받는 라우트가 있는지 확인한다.

    경로만 맞고 메서드가 다르면(Match.PARTIAL, 405) 없는 것으로 본다. 마운트는 안쪽
    라우트로 다시 대조하고, 라우트가 없는 앱(정적 파일)은 변경 요청을 받지 않으므로
    없는 것으로 본다.
    """
    for route in routes:
        match, child_scope = route.matches(scope)
        if match != Match.FULL:
            continue
        if isinstance(route, Mount):
            inner = route.routes
            if inner and route_exists(inner, {**scope, **child_scope}):
                return True
            continue
        return True
    return False


class AuditLogMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        service: str,
        collection,
        identity_extractor: Callable[[Request], Optional[dict]],
    ):
        self.app = app
        self.service = service
        self.collection = collection
        self.identity_extractor = identity_extractor

    def _routes(self, scope: Scope):
        """이 미들웨어가 감싼 앱의 라우트 목록. 찾지 못하면 None(대조 생략, 기록 유지)."""
        app = scope.get("app")
        if hasattr(app, "routes"):
            return app.routes
        node = self.app
        for _ in range(32):
            if node is None:
                break
            if hasattr(node, "routes"):
                return node.routes
            node = getattr(node, "app", None)
        return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        if request.method not in MUTATING_METHODS:
            await self.app(scope, receive, send)
            return

        # 라우팅·인증 미들웨어가 scope를 바꾸기 전 상태로 경로를 대조해야 한다
        match_scope = dict(scope)
        start = time.monotonic()
        status_holder = {"code": None}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)

        try:
            # 존재하지 않는 경로·메서드로 온 요청(스캐너 등)은 기록하지 않는다
            routes = self._routes(scope)
            if routes is not None and not route_exists(routes, match_scope):
                return

            duration_ms = int((time.monotonic() - start) * 1000)
            status_code = status_holder["code"]

            user = None
            try:
                user = self.identity_extractor(request)
            except Exception:
                logger.warning(
                    "identity_extractor 실패 (service=%s)", self.service, exc_info=True
                )
            user = user or {}

            route = scope.get("route")
            path = route.path if route is not None else request.url.path
            action = f"{request.method} {path}"

            insert_log(
                self.collection,
                user.get("uid"),
                action,
                self.service,
                source="auto",
                role=user.get("role"),
                outcome="success" if (status_code and status_code < 400) else "failure",
                request_info={
                    "method": request.method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "ip": request.client.host if request.client else None,
                },
            )
        except Exception:
            logger.warning(
                "AuditLogMiddleware 기록 실패 (service=%s)", self.service, exc_info=True
            )
