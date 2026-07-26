import time
from datetime import datetime, timezone, timedelta

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from db import client

audit_col = client["audit"]["logs"]

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _now_kst_str():
    return (
        datetime.now(timezone.utc)
        .astimezone(timezone(timedelta(hours=9)))
        .strftime("%Y-%m-%d %H:%M:%S")
    )


class AuditLogMiddleware:
    SERVICE = "crawler"

    def __init__(self, app: ASGIApp):
        self.app = app

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
            user = (scope.get("state") or {}).get("user") or {}
            status_code = status_holder["code"]
            audit_col.insert_one(
                {
                    "ts": datetime.now(timezone.utc),
                    "ts_kst": _now_kst_str(),
                    "service": self.SERVICE,
                    "user_uid": user.get("uid"),
                    "user_name": user.get("name"),
                    "role": user.get("role"),
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "success": bool(status_code and status_code < 400),
                    "duration_ms": duration_ms,
                    "ip": request.client.host if request.client else None,
                }
            )
        except Exception:
            pass
