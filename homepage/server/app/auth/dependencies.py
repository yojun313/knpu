from fastapi import Request, HTTPException
from app.auth.jwt import decode_token


def _extract_token(request: Request) -> str | None:
    token = request.cookies.get("session")
    if token:
        return token
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        return authorization[len("Bearer ") :]
    return None


def get_current_user(request: Request) -> dict:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")

    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="유효하지 않은 세션입니다")

    return payload


def get_current_user_optional(request: Request) -> dict | None:
    token = _extract_token(request)
    if not token:
        return None
    return decode_token(token)


def require_admin(request: Request) -> dict:
    user = get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="관리자만 접근할 수 있습니다")
    return user
