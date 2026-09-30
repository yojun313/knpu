"""현재 사용자 확인 — 사이트마다 인증 방식이 달라도 공통 세션 쿠키로 판단한다."""

import logging

logger = logging.getLogger(__name__)


def current_user(request) -> dict | None:
    """로그인(승인된 구성원)이면 {uid, name, role}, 아니면 None."""
    user = (request.scope.get("state") or {}).get("user")
    if user and user.get("uid"):
        return {
            "uid": user["uid"],
            "name": user.get("name") or "",
            "role": user.get("role"),
        }
    token = request.cookies.get("session")
    if not token:
        auth = request.headers.get("Authorization") or ""
        token = auth[7:] if auth.startswith("Bearer ") else None
    if not token:
        return None
    try:
        from system.auth.jwt import decode_token
        from system.auth.session import revalidate_session
        from system.db import user_db

        live = revalidate_session(decode_token(token), user_db)
    except Exception as e:  # 토큰 위조 · DB 장애 모두 비로그인으로 본다
        logger.info("챗봇 세션 확인 실패: %s", e)
        return None
    if not live:
        return None
    return {
        "uid": live.get("sub"),
        "name": live.get("name") or "",
        "role": live.get("role"),
    }
