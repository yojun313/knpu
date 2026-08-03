from fastapi import Request, HTTPException
from app.libs.jwt import decode_token
from app.db import homepage_users_col
from shared.session_check import revalidate_session


def _extract_token(request: Request) -> str | None:
    token = request.cookies.get("session")
    if token:
        return token
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        return authorization[len("Bearer ") :]
    return None


async def get_current_user(request: Request):
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=307, detail="Not logged in")

    payload = decode_token(token)
    live = revalidate_session(payload, homepage_users_col)
    if not live or live.get("role") != "admin":
        raise HTTPException(status_code=307, detail="Not logged in")

    return live
