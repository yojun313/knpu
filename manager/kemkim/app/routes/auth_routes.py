# app/routes/auth_routes.py
import os
import logging

import jwt
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db import user_db
from app.auth.code_store import generate_code, verify_code
from app.auth.jwt import create_token
from app.utils.mail import sendEmail

logger = logging.getLogger(__name__)

router = APIRouter()

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

MODE = int(os.getenv("MODE", 1))


def _safe_next(next_url: str | None) -> str:
    # 오픈 리다이렉트 방지: 같은 오리진의 경로만 허용
    if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
        return "/"
    return next_url


@router.get("/login")
async def login_page(request: Request, next: str = "/"):
    return templates.TemplateResponse(
        request=request, name="login.html", context={"next_url": _safe_next(next)}
    )


@router.post("/auth/request-code")
async def request_code(request: Request):
    body = await request.json()
    name = body.get("name", "").strip()

    if not name:
        return JSONResponse(status_code=400, content={"detail": "이름을 입력해주세요"})

    user = user_db.find_one({"name": name}, {"_id": 0})
    if not user:
        return JSONResponse(
            status_code=404, content={"detail": "등록되지 않은 사용자입니다"}
        )

    email = user["email"]
    uid = user["uid"]
    code = generate_code(name, email, uid)

    try:
        sendEmail(
            receiver=email,
            title="[KEMKIM VIEWER] 로그인 인증코드",
            text=f"인증코드: {code}\n\n5분 내에 입력해주세요.",
        )
    except Exception:
        logger.exception(f"인증코드 이메일 발송 실패: {name}")
        return JSONResponse(
            status_code=500, content={"detail": "이메일 발송에 실패했습니다"}
        )

    return {"message": "인증코드가 전송되었습니다"}


@router.post("/auth/verify-code")
async def verify_code_endpoint(request: Request):
    body = await request.json()
    name = body.get("name", "").strip()
    code = body.get("code", "").strip()

    if not name or not code:
        return JSONResponse(
            status_code=400, content={"detail": "이름과 인증코드를 입력해주세요"}
        )

    user_data = verify_code(name, code)
    if not user_data:
        return JSONResponse(
            status_code=401,
            content={"detail": "인증코드가 올바르지 않거나 만료되었습니다"},
        )

    token = create_token(user_data)

    response = JSONResponse(
        content={"message": "로그인 성공", "name": user_data["name"]}
    )
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        secure=(MODE == 1),
        samesite="lax",
        max_age=7776000,
        path="/",
    )
    return response


@router.post("/auth/logout")
async def logout():
    response = JSONResponse(content={"message": "로그아웃 완료"})
    response.delete_cookie(key="session", path="/")
    return response


@router.get("/auth/direct-login")
async def direct_token_login(token: str, next: str = "/"):
    """데스크톱 MANAGER 앱이 이미 가진(만료 없는) 토큰으로 자동 로그인.
    새 토큰을 발급하지 않고, 넘어온 토큰을 그대로 세션 쿠키로 재사용한다.
    (crawler/app/routes/auth_routes.py의 동일 패턴)"""
    try:
        payload = jwt.decode(
            token, os.getenv("JWT_SECRET"), algorithms=[os.getenv("JWT_ALGORITHM")]
        )
    except jwt.InvalidTokenError:
        return JSONResponse(
            status_code=401, content={"detail": "유효하지 않은 토큰입니다"}
        )

    user = user_db.find_one({"uid": payload["sub"]}, {"_id": 0})
    if not user:
        return JSONResponse(
            status_code=404, content={"detail": "사용자를 찾을 수 없습니다"}
        )

    if payload.get("device") and payload["device"] not in user.get("device_list", []):
        return JSONResponse(
            status_code=404, content={"detail": "등록되지 않은 기기입니다"}
        )

    response = RedirectResponse(url=_safe_next(next))
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        secure=(MODE == 1),
        samesite="lax",
        max_age=7776000,
        path="/",
    )
    return response
