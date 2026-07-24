import os
import jwt


def get_uid_from_bearer(authorization: str | None) -> str | None:
    """'Bearer <token>' 헤더에서 uid를 뽑아낸다. 실패하면 None (호출부는 인증 실패를
    막지 않고 그냥 uid 없이 진행 — 네트워크 분석 자체는 로그인 여부와 무관하게 동작해야 함)."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[len("Bearer ") :]
    try:
        payload = jwt.decode(
            token, os.getenv("JWT_SECRET"), algorithms=[os.getenv("JWT_ALGORITHM")]
        )
        return payload.get("sub")
    except jwt.InvalidTokenError:
        return None
