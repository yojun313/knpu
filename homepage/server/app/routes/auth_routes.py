import os
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, Response, HTTPException
from fastapi.responses import RedirectResponse

from app.models import (
    SignupRequest,
    VerifyEmailRequest,
    ResendCodeRequest,
    LoginRequest,
    UpdateProfileRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UpdateRoleRequest,
)
from app.auth import service
from app.auth.jwt import decode_token
from app.auth.dependencies import (
    get_current_user,
    get_current_user_optional,
    require_admin,
)

router = APIRouter()

MODE = int(os.getenv("MODE", 1))
COOKIE_DOMAIN = ".knpu.re.kr" if MODE == 1 else None
COOKIE_SECURE = MODE == 1
COOKIE_MAX_AGE = 30 * 24 * 60 * 60


def _set_session_cookie(response: Response, token: str):
    response.set_cookie(
        key="session",
        value=token,
        max_age=COOKIE_MAX_AGE,
        domain=COOKIE_DOMAIN,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )


@router.post("/signup")
def signup(data: SignupRequest):
    return service.signup(data)


@router.post("/verify-email")
def verify_email(data: VerifyEmailRequest):
    return service.verify_email(data)


@router.post("/resend-code")
def resend_code(data: ResendCodeRequest):
    return service.resend_signup_code(data.username)


@router.post("/login")
def login(data: LoginRequest, response: Response):
    result = service.login(data)
    _set_session_cookie(response, result["token"])
    return result


def _safe_redirect(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname == "knpu.re.kr" or (parsed.hostname or "").endswith(
        ".knpu.re.kr"
    ):
        return url
    return "https://knpu.re.kr/account"


@router.get("/token-login")
def token_login(token: str, redirect: str, response: Response):
    """MANAGER 데스크톱 앱이 이미 보유한(로그인 시 발급된) 토큰을 시스템 기본 브라우저에도
    심어주기 위한 핸드오프. 뷰어(kemkim/network 등) 딥링크를 시스템 브라우저로 열 때 쓴다."""
    if not decode_token(token):
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    redirect_response = RedirectResponse(url=_safe_redirect(redirect))
    _set_session_cookie(redirect_response, token)
    return redirect_response


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("session", domain=COOKIE_DOMAIN, path="/")
    return {"message": "로그아웃되었습니다"}


@router.get("/me")
def me(user=Depends(get_current_user)):
    return service.get_profile(user["sub"])


@router.get("/me/optional")
def me_optional(user=Depends(get_current_user_optional)):
    if not user:
        return None
    return service.get_profile(user["sub"])


@router.patch("/me")
def update_me(data: UpdateProfileRequest, user=Depends(get_current_user)):
    return service.update_profile(user["sub"], data)


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest):
    return service.forgot_password(data.username)


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest):
    return service.reset_password(data)


@router.get("/admin/requests")
def list_requests(admin=Depends(require_admin)):
    return service.list_pending_requests()


@router.post("/admin/requests/{uid}/approve")
def approve_request(uid: str, admin=Depends(require_admin)):
    return service.approve_request(uid, admin["sub"])


@router.post("/admin/requests/{uid}/reject")
def reject_request(uid: str, admin=Depends(require_admin)):
    return service.reject_request(uid)


@router.post("/admin/users/{uid}/role")
def update_role(uid: str, data: UpdateRoleRequest, admin=Depends(require_admin)):
    return service.change_role(uid, data.role, admin["sub"])
