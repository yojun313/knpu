import secrets

SESSION_COOKIE_NAME = "session_id"

_SESSIONS: dict[str, dict] = {}


def get_session(request) -> tuple[str, dict]:
    sid = request.cookies.get(SESSION_COOKIE_NAME)
    if sid and sid in _SESSIONS:
        return sid, _SESSIONS[sid]
    sid = secrets.token_hex(16)
    _SESSIONS[sid] = {}
    return sid, _SESSIONS[sid]


def attach_session_cookie(response, sid: str) -> None:
    response.set_cookie(SESSION_COOKIE_NAME, sid, httponly=True, samesite="lax")
