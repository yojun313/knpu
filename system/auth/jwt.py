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
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except PyJWTError:
        return None


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    payload = decode_token(credentials.credentials)
    live = revalidate_session(payload, user_db)
    if not live:
        raise HTTPException(status_code=401, detail="Invalid token")
    return live["sub"]
