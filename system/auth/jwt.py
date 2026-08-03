import os

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError

from system.auth.session import revalidate_session
from system.db import user_db

SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = os.getenv("JWT_ALGORITHM")
security = HTTPBearer()


def decode_token(token: str) -> dict | None:
    """서명·만료만 검증한 원본 JWT payload. 계정 상태(승인/삭제/권한 변경)는 보지 않는다 —
    그 확인이 필요하면 revalidate_session에 넘겨라."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except PyJWTError:
        return None


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """FastAPI Depends용. Bearer 토큰 -> uid(sub) 문자열. (manager/server 라우트가 쓰던 방식)"""
    payload = decode_token(credentials.credentials)
    live = revalidate_session(payload, user_db)
    if not live:
        raise HTTPException(status_code=401, detail="Invalid token")
    return live["sub"]
