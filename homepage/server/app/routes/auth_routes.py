from urllib.parse import urlparse
from fastapi import APIRouter, Depends, Request, Response, HTTPException
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
    PasskeyRegisterVerifyRequest,
    PasskeyLoginVerifyRequest,
    PasskeyClientErrorRequest,
)
from app.auth import service, webauthn_service
from app.auth.webauthn_config import BASE_URL
from app.auth.jwt import decode_token
from app.db import users_db
from app.libs.discord_notify import notify_discord
from app.auth.dependencies import (
    get_current_user,
    get_current_user_optional,
    require_admin,
)
from system.auth.session import revalidate_session

router = APIRouter()

COOKIE_DOMAIN = ".knpu.re.kr"
COOKIE_SECURE = True
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
    return f"{BASE_URL}/account"


@router.get("/token-login")
def token_login(token: str, redirect: str, response: Response):
    if not revalidate_session(decode_token(token), users_db):
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
    return service.reject_request(uid, admin["sub"])


@router.post("/admin/users/{uid}/role")
def update_role(uid: str, data: UpdateRoleRequest, admin=Depends(require_admin)):
    return service.change_role(uid, data.role, admin["sub"])


@router.delete("/admin/users/{uid}")
def delete_user(uid: str, admin=Depends(require_admin)):
    return service.delete_user(uid, admin["sub"])


# ---------------- Passkey (WebAuthn) ----------------
# 로그인 상태에서 새 패스키를 등록하는 흐름(계정 설정 페이지에서 사용).


@router.post("/passkey/register/options")
def passkey_register_options(user=Depends(get_current_user)):
    options_json = webauthn_service.get_registration_options(user["sub"])
    return Response(content=options_json, media_type="application/json")


@router.post("/passkey/register/verify")
def passkey_register_verify(
    data: PasskeyRegisterVerifyRequest, user=Depends(get_current_user)
):
    return webauthn_service.verify_registration(
        user["sub"], data.credential, data.device_name
    )


# 로그인 화면에서 아이디 입력 없이 바로 패스키로 로그인하는 흐름 — 아직 세션이 없으므로
# 인증이 필요 없다(로그인 그 자체이기 때문).


@router.post("/passkey/login/options")
def passkey_login_options():
    options_json = webauthn_service.get_authentication_options()
    return Response(content=options_json, media_type="application/json")


@router.post("/passkey/login/verify")
def passkey_login_verify(data: PasskeyLoginVerifyRequest, response: Response):
    result = webauthn_service.verify_authentication(data.credential)
    _set_session_cookie(response, result["token"])
    return result


@router.get("/passkey/list")
def passkey_list(user=Depends(get_current_user)):
    return {"passkeys": webauthn_service.list_passkeys(user["sub"])}


@router.delete("/passkey/{credential_id}")
def passkey_delete(credential_id: str, user=Depends(get_current_user)):
    return webauthn_service.delete_passkey(user["sub"], credential_id)


_PASSKEY_IGNORED_ERROR_NAMES = {"NotAllowedError", "AbortError"}


@router.post("/passkey/client-error")
def passkey_client_error(data: PasskeyClientErrorRequest, request: Request):
    if data.name in _PASSKEY_IGNORED_ERROR_NAMES:
        return {"message": "ignored"}

    user_agent = request.headers.get("user-agent", "-")
    notify_discord(
        "system_error",
        f"[HOMEPAGE] 패스키 {data.context} 실패 (브라우저)\n"
        f"[{data.name or 'Error'}] {data.message or '(메시지 없음)'}\n"
        f"UA: {user_agent}",
    )
    return {"message": "logged"}
