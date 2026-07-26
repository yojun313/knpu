"""변경(POST/PUT/PATCH/DELETE) 요청을 사용자별로 구조화해 공용 audit.logs 컬렉션에 기록한다.
GET 등 조회 요청은 노이즈가 커서 기록하지 않는다. 4개 서비스(crawler/homepage/manager/admin)가
각자 같은 스키마로 이 컬렉션에 기록하며, admin 대시보드에서 서비스 구분 없이 한 번에 조회한다.

BaseHTTPMiddleware가 아니라 순수 ASGI 미들웨어로 작성한다 — AuthMiddleware와 동일하게
StreamingResponse hang 문제를 피하기 위함이다.
"""

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
