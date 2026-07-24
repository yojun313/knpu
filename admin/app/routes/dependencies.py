from fastapi import Request, HTTPException
from app.libs.jwt import decode_token


async def get_current_user(request: Request):
    """knpu.re.kr(homepage) 중앙 로그인이 발급한 session 쿠키를 검증하고,
    role이 admin인 계정만 대시보드 접근을 허용한다."""
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=307, detail="Not logged in")

    payload = decode_token(token)
    if not payload or payload.get("role") != "admin":
        raise HTTPException(status_code=307, detail="Not logged in")

    return payload
