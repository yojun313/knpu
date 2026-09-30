"""설정 창(모든 KNPU 사이트 네비바 ⚙)의 '내 계정' · '로컬 AI API' 섹션 API.

mount_shared_ui 가 /shared-ui/account/api/* 로 붙인다. /shared-ui/* 는 각 사이트 인증 미들웨어가
통과시키는 경로라서, 로그인 여부는 공통 세션 쿠키로 여기서 직접 확인한다.
홈페이지 계정 화면과 같은 규칙을 쓴다: 비밀번호는 bcrypt, 비밀번호를 바꾸면 token_version 을 올려
다른 기기 세션을 모두 끊는다. 패스키 등록은 WebAuthn 이 홈페이지 도메인에 묶여 있어 홈페이지에서 한다.
"""

import logging
import os
from datetime import datetime

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

_NO_STORE = {"cache-control": "no-store"}


def _session_user(request: Request) -> dict:
    """승인된 로그인 사용자의 DB 문서(비밀값 제외). 아니면 401."""
    from system.auth.jwt import decode_token
    from system.auth.session import revalidate_session
    from system.db import user_db

    token = request.cookies.get("session")
    if not token:
        auth = request.headers.get("Authorization") or ""
        token = auth[7:] if auth.startswith("Bearer ") else None
    live = None
    if token:
        try:
            live = revalidate_session(decode_token(token), user_db)
        except Exception:
            live = None
    if not live:
        raise HTTPException(401, "로그인이 필요합니다.")
    user = user_db.find_one({"uid": live["sub"]})
    if not user:
        raise HTTPException(401, "로그인이 필요합니다.")
    return user


def _log(uid: str, action: str, message: str) -> None:
    try:
        from system.db import user_logs_db
        from system.logging.user_log import insert_log

        insert_log(
            user_logs_db, uid, action, "settings", message=message, outcome="success"
        )
    except Exception:
        pass


def _fmt(value) -> str | None:
    return (
        value.strftime("%Y-%m-%d %H:%M")
        if isinstance(value, datetime)
        else (str(value) if value else None)
    )


def _profile(user: dict) -> dict:
    from system.db import members_db

    member = None
    if user.get("member_uid"):
        try:
            m = members_db.find_one(
                {"uid": user["member_uid"]},
                {"_id": 0, "name": 1, "section": 1, "position": 1, "image": 1},
            )
            member = m or None
        except Exception:
            member = None
    return {
        "uid": user["uid"],
        "username": user.get("username"),
        "name": user.get("name"),
        "email": user.get("email"),
        "email_verified": bool(user.get("email_verified")),
        "role": user.get("role"),
        "status": user.get("status"),
        "created_at": _fmt(user.get("created_at")),
        "updated_at": _fmt(user.get("updated_at")),
        "member": member,
    }


def lab_llm_info() -> dict:
    """구성원에게 안내하는 연구실 로컬 AI API 접속 정보(.env 에서 읽는다)."""
    base = (os.getenv("LAB_LLM_PUBLIC_URL") or "https://llm0.knpu.re.kr/v1").rstrip("/")
    token = os.getenv("LAB_LLM_PUBLIC_TOKEN") or os.getenv("LLM_API_KEY") or ""
    return {"base_url": base, "token": token, "token_set": bool(token)}


def register(app) -> None:
    base = "/shared-ui/account/api"
    register_lab_llm_test(app)  # /lab-llm/models 를 /lab-llm 보다 먼저 등록

    @app.get(f"{base}/me", include_in_schema=False)
    def account_me(request: Request):
        return JSONResponse(_profile(_session_user(request)), headers=_NO_STORE)

    @app.patch(f"{base}/me", include_in_schema=False)
    async def account_update(request: Request):
        from system.db import user_db

        user = _session_user(request)
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(400, "요청 형식이 올바르지 않습니다.")
        updates: dict = {}
        name = str(body.get("name") or "").strip()
        if name and name != user.get("name"):
            if len(name) > 40:
                raise HTTPException(400, "이름은 40자 이하로 입력해 주세요.")
            updates["name"] = name
        new_pw = body.get("new_password")
        if new_pw:
            import bcrypt

            cur = str(body.get("current_password") or "")
            if not cur or not bcrypt.checkpw(
                cur.encode(), str(user.get("password_hash") or "").encode()
            ):
                raise HTTPException(401, "현재 비밀번호가 올바르지 않습니다.")
            if len(str(new_pw)) < 8:
                raise HTTPException(400, "비밀번호는 8자 이상이어야 합니다.")
            updates["password_hash"] = bcrypt.hashpw(
                str(new_pw).encode(), bcrypt.gensalt()
            ).decode()
        if not updates:
            return JSONResponse(_profile(user), headers=_NO_STORE)
        updates["updated_at"] = datetime.now()
        ops = {"$set": updates}
        if "password_hash" in updates:
            # 홈페이지와 같은 규칙: 비밀번호가 바뀌면 다른 기기의 세션을 모두 끊는다
            ops["$inc"] = {"token_version": 1}
        user_db.update_one({"uid": user["uid"]}, ops)
        labels = {"name": "이름", "password_hash": "비밀번호"}
        _log(
            user["uid"],
            "settings.profile.update",
            "설정 창에서 프로필 수정: "
            + ", ".join(labels[k] for k in labels if k in updates),
        )
        fresh = user_db.find_one({"uid": user["uid"]})
        out = _profile(fresh)
        out["relogin"] = "password_hash" in updates
        return JSONResponse(out, headers=_NO_STORE)

    @app.get(f"{base}/passkeys", include_in_schema=False)
    def account_passkeys(request: Request):
        from system.db import webauthn_credentials_db

        user = _session_user(request)
        items = []
        for d in webauthn_credentials_db.find(
            {"user_uid": user["uid"]}, {"public_key": 0, "sign_count": 0}
        ).sort("created_at", -1):
            items.append(
                {
                    "credential_id": d["_id"],
                    "device_name": d.get("device_name") or "패스키",
                    "backed_up": bool(d.get("backed_up")),
                    "created_at": _fmt(d.get("created_at")),
                    "last_used_at": _fmt(d.get("last_used_at")),
                }
            )
        return JSONResponse({"passkeys": items}, headers=_NO_STORE)

    @app.delete(f"{base}/passkeys/{{credential_id}}", include_in_schema=False)
    def account_passkey_delete(request: Request, credential_id: str):
        from system.db import webauthn_credentials_db

        user = _session_user(request)
        res = webauthn_credentials_db.delete_one(
            {"_id": credential_id, "user_uid": user["uid"]}
        )
        if res.deleted_count == 0:
            raise HTTPException(404, "패스키를 찾을 수 없습니다.")
        _log(user["uid"], "settings.passkey.delete", "설정 창에서 패스키 삭제")
        return {"ok": True}

    @app.post(f"{base}/logout-all", include_in_schema=False)
    def account_logout_all(request: Request):
        """모든 기기에서 로그아웃: 세션 버전을 올려 발급된 세션을 전부 무효로 만든다."""
        from system.db import user_db

        user = _session_user(request)
        user_db.update_one(
            {"uid": user["uid"]},
            {"$inc": {"token_version": 1}, "$set": {"updated_at": datetime.now()}},
        )
        _log(user["uid"], "settings.logout_all", "모든 기기에서 로그아웃")
        return {"ok": True}

    @app.get(f"{base}/lab-llm", include_in_schema=False)
    def account_lab_llm(request: Request):
        # 토큰은 로그인한 연구실 구성원에게만 보여 준다
        _session_user(request)
        return JSONResponse(lab_llm_info(), headers=_NO_STORE)


def register_lab_llm_test(app) -> None:
    """로컬 AI API 연결 확인: 서버에서 {base}/models 를 불러 모델 목록을 돌려준다(브라우저 CORS 우회)."""

    @app.get("/shared-ui/account/api/lab-llm/models", include_in_schema=False)
    def account_lab_llm_models(request: Request):
        import httpx

        _session_user(request)
        info = lab_llm_info()
        headers = {"Authorization": f"Bearer {info['token']}"} if info["token"] else {}
        try:
            r = httpx.get(f"{info['base_url']}/models", headers=headers, timeout=10.0)
        except httpx.HTTPError as e:
            return JSONResponse(
                {"ok": False, "error": f"연결하지 못했습니다: {type(e).__name__}"},
                headers=_NO_STORE,
            )
        if r.status_code != 200:
            return JSONResponse(
                {
                    "ok": False,
                    "error": f"HTTP {r.status_code} (토큰을 확인하세요)"
                    if r.status_code == 401
                    else f"HTTP {r.status_code}",
                },
                headers=_NO_STORE,
            )
        try:
            models = [m.get("id") for m in (r.json().get("data") or []) if m.get("id")]
        except ValueError:
            models = []
        return JSONResponse({"ok": True, "models": models}, headers=_NO_STORE)
