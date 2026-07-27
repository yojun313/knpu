from fastapi import Request, HTTPException
from app.libs.jwt import decode_token


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
    if not payload or payload.get("role") != "admin":
        raise HTTPException(status_code=307, detail="Not logged in")

    return payload
