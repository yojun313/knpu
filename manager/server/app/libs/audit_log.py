"""변경(POST/PUT/PATCH/DELETE) 요청을 사용자별로 구조화해 공용 audit.logs 컬렉션에 기록한다.
GET 등 조회 요청은 노이즈가 커서 기록하지 않는다. crawler/homepage/admin과 동일한 스키마를 쓴다."""

import os
import time
from datetime import datetime, timezone, timedelta

import jwt as pyjwt
from jwt import PyJWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.db import client

audit_col = client["audit"]["logs"]

SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = os.getenv("JWT_ALGORITHM")

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _now_kst_str():
    return (
        datetime.now(timezone.utc)
        .astimezone(timezone(timedelta(hours=9)))
        .strftime("%Y-%m-%d %H:%M:%S")
    )


def _decode(request: Request) -> dict | None:
    token = request.cookies.get("session")
    if not token:
        authorization = request.headers.get("Authorization")
        if authorization and authorization.startswith("Bearer "):
            token = authorization[len("Bearer ") :]
    if not token:
        return None
    try:
        return pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except PyJWTError:
        return None


class AuditLogMiddleware(BaseHTTPMiddleware):
    SERVICE = "manager"

    async def dispatch(self, request: Request, call_next):
        if request.method not in MUTATING_METHODS:
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)

        try:
            duration_ms = int((time.monotonic() - start) * 1000)
            payload = _decode(request)
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
