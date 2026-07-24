import secrets

SESSION_COOKIE_NAME = "session_id"

_SESSIONS: dict[str, dict] = {}


def get_session(request) -> tuple[str, dict]:
    """요청의 session_id 쿠키로 서버 메모리에 있는 세션 dict를 찾거나 새로 만든다.
    세션 데이터(주민등록번호 등 PII 포함)는 서버 메모리에만 있고, 쿠키엔 세션ID만 담긴다."""
    sid = request.cookies.get(SESSION_COOKIE_NAME)
    if sid and sid in _SESSIONS:
        return sid, _SESSIONS[sid]
    sid = secrets.token_hex(16)
    _SESSIONS[sid] = {}
    return sid, _SESSIONS[sid]


def attach_session_cookie(response, sid: str) -> None:
    response.set_cookie(SESSION_COOKIE_NAME, sid, httponly=True, samesite="lax")
