import os
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from auth.jwt import verify_token

router = APIRouter()

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

MODE = int(os.getenv("MODE", 1))
COOKIE_SECURE = MODE == 1
COOKIE_MAX_AGE = 30 * 24 * 60 * 60


@router.get("/")
async def dashboard_page(request: Request):
    user = getattr(request.state, "user", None)
    username = user.get("name", "") if user else ""
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "username": username,
        },
    )


@router.get("/auth/token-login")
async def token_login(token: str):
    """매니저 앱(데스크톱)이 이미 가진 로그인 토큰으로 크롤러 대시보드에 자동 로그인한다.
    매니저 앱 내 임베디드 브라우저가 별도 프로필이라 knpu.re.kr 세션 쿠키를 공유하지 못하는
    경우에도, 토큰을 쿼리로 넘겨받아 이 서버가 직접 session 쿠키를 심어준다."""
    payload = verify_token(token)
    if not payload:
        return RedirectResponse(url="https://knpu.re.kr/login")

    response = RedirectResponse(url="/")
    response.set_cookie(
        key="session",
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )
    return response
