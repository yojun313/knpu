import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
KST = ZoneInfo("Asia/Seoul")


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
        entry = build_entry(user_uid, action, service, **kwargs)
        collection.insert_one(entry)
    except Exception:
        logger.warning(
            "user_log insert 실패 (action=%s, service=%s)",
            action,
            service,
            exc_info=True,
        )


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

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        if request.method not in MUTATING_METHODS:
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        status_holder = {"code": None}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)

        try:
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
