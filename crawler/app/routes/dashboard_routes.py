import os
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from system.auth.jwt import decode_token as verify_token
from system.endpoints import LOGIN_URL

router = APIRouter()

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

# dev(dev-crawler.knpu.re.kr)도 https로 서빙되므로 MODE와 무관하게 Secure를 켠다.
COOKIE_SECURE = True
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
            "is_admin": bool(user and user.get("role") == "admin"),
            "my_uid": user.get("uid") if user else None,
        },
    )


@router.get("/auth/token-login")
async def token_login(token: str):
    payload = verify_token(token)
    if not payload:
        return RedirectResponse(url=LOGIN_URL)

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
