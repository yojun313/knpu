import os
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from db import get_userinfo, user_db
from auth.code_store import generate_code, verify_code
from auth.jwt import create_token
from common.notification import sendMail
from config import MODE
import logging
import jwt

logger = logging.getLogger(__name__)

router = APIRouter()

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

@router.get("/login")
async def login_page(request: Request):
    """로그인 페이지 렌더링"""
    return templates.TemplateResponse(
        request=request,
        name="login.html"
    )

@router.post("/auth/request-code")
async def request_code(request: Request):
    """이름으로 사용자 조회 → 이메일로 인증코드 발송"""
    body = await request.json()
    name = body.get("name", "").strip()

    if not name:
        return JSONResponse(status_code=400, content={"detail": "이름을 입력해주세요"})

    # DB에서 사용자 조회
    user_info = get_userinfo(name)
    if not user_info:
        return JSONResponse(status_code=404, content={"detail": "등록되지 않은 사용자입니다"})

    email = user_info["Email"]
    uid = user_info["userUid"]

    # 인증코드 생성
    code = generate_code(name, email, uid)

    # 이메일 발송
    try:
        sendMail(
            receiver=email,
            title="[PAILAB CRAWLER] 로그인 인증코드",
            text=f"인증코드: {code}\n\n5분 내에 입력해주세요.",
        )
    except Exception as e:
        logger.exception(f"인증코드 이메일 발송 실패: {name}")
        return JSONResponse(status_code=500, content={"detail": "이메일 발송에 실패했습니다"})

    return {"message": "인증코드가 전송되었습니다"}


@router.post("/auth/verify-code")
async def verify_code_endpoint(request: Request):
    """인증코드 검증 → JWT 생성 → Set-Cookie"""
    body = await request.json()
    name = body.get("name", "").strip()
    code = body.get("code", "").strip()

    if not name or not code:
        return JSONResponse(status_code=400, content={"detail": "이름과 인증코드를 입력해주세요"})

    # 코드 검증
    user_data = verify_code(name, code)
    if not user_data:
        return JSONResponse(status_code=401, content={"detail": "인증코드가 올바르지 않거나 만료되었습니다"})

    # JWT 생성
    token = create_token(user_data)

    # Cookie 설정 + 응답
    response = JSONResponse(content={"message": "로그인 성공", "name": user_data["name"]})
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        secure=(MODE == 1),     
        samesite="lax",
        max_age=7776000,        
        path="/",
    )

    logger.info(f"로그인 성공: {user_data['name']}")
    return response


@router.post("/auth/logout")
async def logout():
    """로그아웃 → cookie 삭제"""
    response = JSONResponse(content={"message": "로그아웃 완료"})
    response.delete_cookie(key="session", path="/")
    return response


@router.get("/auth/direct-login")
async def direct_token_login(token: str):
    if not token:
        return JSONResponse(status_code=400, content={"detail": "토큰이 필요합니다"})
    
    payload = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=[os.getenv("JWT_ALGORITHM")])
    user = user_db.find_one({"uid": payload["sub"]}, {"_id": 0})
    
    if not user:
        raise NotFoundException("User not found")

    if payload["device"] not in user.get("device_list", []):
        raise NotFoundException("Device not registered")
    
    response = RedirectResponse(url="/")
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