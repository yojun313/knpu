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
            "is_admin": bool(user and user.get("role") == "admin"),
            "my_uid": user.get("uid") if user else None,
        },
    )


@router.get("/auth/token-login")
async def token_login(token: str):
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
