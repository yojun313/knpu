import time
from datetime import datetime, timezone, timedelta

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.db import client
from app.libs.jwt import decode_token

audit_col = client["audit"]["logs"]

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _now_kst_str():
    return (
        datetime.now(timezone.utc)
        .astimezone(timezone(timedelta(hours=9)))
        .strftime("%Y-%m-%d %H:%M:%S")
    )


class AuditLogMiddleware(BaseHTTPMiddleware):
    SERVICE = "admin"

    async def dispatch(self, request: Request, call_next):
        if request.method not in MUTATING_METHODS:
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)

        try:
            duration_ms = int((time.monotonic() - start) * 1000)
            token = request.cookies.get("session")
            payload = decode_token(token) if token else None
            audit_col.insert_one(
                {
                    "ts": datetime.now(timezone.utc),
                    "ts_kst": _now_kst_str(),
                    "service": self.SERVICE,
                    "user_uid": payload.get("sub") if payload else None,
                    "user_name": payload.get("name") if payload else None,
                    "role": payload.get("role") if payload else None,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "success": response.status_code < 400,
                    "duration_ms": duration_ms,
                    "ip": request.client.host if request.client else None,
                }
            )
        except Exception:
            pass

        return response
