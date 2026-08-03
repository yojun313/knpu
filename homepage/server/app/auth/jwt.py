import os
import jwt
from datetime import datetime, timedelta, timezone
from jwt import PyJWTError

SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = os.getenv("JWT_ALGORITHM")
TOKEN_EXPIRE_DAYS = 30


def create_token(user: dict) -> str:
    payload = {
        "sub": user["uid"],
        "name": user["name"],
        "role": user["role"],
        "tv": user.get("token_version", 1),
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except PyJWTError:
        return None
