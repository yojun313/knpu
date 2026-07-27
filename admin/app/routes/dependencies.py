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
    """knpu.re.kr(homepage) 중앙 로그인이 발급한 session 쿠키(브라우저) 또는 같은
    JWT_SECRET으로 서명된 Bearer 토큰(디스코드 봇 등 서버간 호출)을 검증하고,
    role이 admin인 계정만 대시보드/API 접근을 허용한다."""
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=307, detail="Not logged in")

    payload = decode_token(token)
    if not payload or payload.get("role") != "admin":
        raise HTTPException(status_code=307, detail="Not logged in")

    return payload
