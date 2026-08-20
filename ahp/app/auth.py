from datetime import datetime, timedelta, timezone

import jwt as pyjwt
from fastapi import Request, WebSocket, HTTPException
from fastapi.concurrency import run_in_threadpool

from system.auth.jwt import decode_token, SECRET_KEY, ALGORITHM
from system.auth.session import revalidate_session
from system.db import user_db

RESPONDENT_TOKEN_TYPE = "ahp_respondent"
RESPONDENT_TOKEN_TTL_DAYS = 30


def current_user(request: Request) -> dict:
    user = request.scope.get("state", {}).get("user")
    if not user:
        # AuthMiddleware가 /api/*는 이미 401로 막아주므로 정상 흐름에서는 도달하지 않는다.
        raise HTTPException(401, "인증이 필요합니다")
    return user


def current_uid(request: Request) -> str:
    return current_user(request)["uid"]


def is_admin(request: Request) -> bool:
    return current_user(request).get("role") == "admin"


def require_admin(request: Request) -> dict:
    user = current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "관리자만 접근할 수 있습니다")
    return user


def _decode_and_revalidate_sync(token: str) -> dict | None:
    payload = decode_token(token)
    return revalidate_session(payload, user_db)


async def authenticate_websocket(ws: WebSocket) -> dict | None:
    token = ws.cookies.get("session")
    if not token:
        auth_header = ws.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer ") :]
    if not token:
        return None
    live = await run_in_threadpool(_decode_and_revalidate_sync, token)
    if not live:
        return None
    return {"uid": live["sub"], "name": live["name"], "role": live.get("role")}


# ── 응답자 세션 토큰 ─────────────────────────────────────────────────────────
# 관리자 세션(system.auth의 JWT)과 같은 SECRET_KEY/ALGORITHM을 그대로 쓰지만,
# typ 클레임으로 종류를 분리해 둔다 — 응답자 토큰이 관리자 토큰으로 오인되거나
# 그 반대로 쓰이는 사고를 애초에 구조적으로 막는다(응답자는 로그인 계정이 없다).
def create_respondent_token(respondent_id: str, collection_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "typ": RESPONDENT_TOKEN_TYPE,
        "respondent_id": respondent_id,
        "collection_id": collection_id,
        "iat": now,
        "exp": now + timedelta(days=RESPONDENT_TOKEN_TTL_DAYS),
    }
    return pyjwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_respondent_token(token: str) -> dict | None:
    try:
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except pyjwt.PyJWTError:
        return None
    if payload.get("typ") != RESPONDENT_TOKEN_TYPE:
        return None
    return payload


def current_respondent(request: Request) -> dict:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "응답자 인증이 필요합니다")
    payload = verify_respondent_token(auth_header[len("Bearer ") :])
    if not payload:
        raise HTTPException(
            401, "세션이 만료되었거나 유효하지 않습니다. 코드를 다시 입력해 주세요"
        )
    return payload
