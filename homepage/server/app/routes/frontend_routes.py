import os
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse

from app.auth.dependencies import get_current_user_optional
from app.db import discord_link_col, users_db

router = APIRouter()

PUBLIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")

DISCORD_LINK_EXPIRE_MINUTES = 10


def _page(filename: str) -> FileResponse:
    return FileResponse(os.path.join(PUBLIC_DIR, filename))


@router.get("/")
def home():
    return _page("homepage.html")


@router.get("/about")
def about():
    return _page("about.html")


@router.get("/admission")
def admission():
    return _page("admission.html")


@router.get("/publications")
def publications():
    return _page("publications.html")


@router.get("/news")
def news():
    return _page("news.html")


@router.get("/people")
def people():
    return _page("people.html")


@router.get("/gallery")
def gallery():
    return _page("gallery.html")


@router.get("/systems")
def systems():
    return _page("systems.html")


@router.get("/terms")
def terms():
    return _page("terms.html")


@router.get("/login")
def login_page():
    return _page("login.html")


@router.get("/signup")
def signup_page():
    return _page("signup.html")


@router.get("/verify-email")
def verify_email_page():
    return _page("verify-email.html")


@router.get("/account")
def account_page(user=Depends(get_current_user_optional)):
    if not user:
        return RedirectResponse(url="/login?redirect=%2Faccount")
    return _page("account.html")


@router.get("/admin")
def admin_page(user=Depends(get_current_user_optional)):
    if not user:
        return RedirectResponse(url="/login?redirect=%2Fadmin")
    if user.get("role") != "admin":
        return RedirectResponse(url="/account")
    return _page("admin.html")


def _discord_link_page(title: str, message: str, ok: bool) -> HTMLResponse:
    color = "#22c55e" if ok else "#ef4444"
    html = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  body {{ margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center;
    background:#111827; color:#e5e7eb; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
  .card {{ max-width:420px; padding:2.2rem; border-radius:16px; background:#1f2937; text-align:center;
    box-shadow:0 10px 40px rgba(0,0,0,.4); }}
  .icon {{ font-size:2.4rem; margin-bottom:.6rem; }}
  h1 {{ font-size:1.15rem; margin:0 0 .6rem; color:{color}; }}
  p {{ font-size:.9rem; color:#9ca3af; line-height:1.5; margin:0; }}
</style></head>
<body><div class="card">
  <div class="icon">{"✅" if ok else "⚠️"}</div>
  <h1>{title}</h1>
  <p>{message}</p>
</div></body></html>"""
    return HTMLResponse(html)


@router.get("/discord-link")
def discord_link(token: str = "", user=Depends(get_current_user_optional)):
    """디스코드 인증 버튼 → knpu.re.kr 로그인 → 자동 인증 연동.
    bot/cogs/cog_verify.py가 만든 1회용 토큰을 이 페이지에서 로그인 상태로 소비한다."""
    if not user:
        return RedirectResponse(
            url=f"/login?redirect=%2Fdiscord-link%3Ftoken%3D{token}"
        )

    req_doc = discord_link_col.find_one({"token": token})
    if not req_doc:
        return _discord_link_page(
            "유효하지 않은 링크", "디스코드에서 인증 버튼을 다시 눌러주세요.", False
        )

    if req_doc.get("status") != "pending":
        return _discord_link_page(
            "이미 처리된 링크",
            "이미 인증이 완료되었거나 만료된 링크입니다. 디스코드로 돌아가주세요.",
            False,
        )

    created_at = req_doc.get("created_at")
    if created_at and created_at.replace(tzinfo=timezone.utc) < datetime.now(
        timezone.utc
    ) - timedelta(minutes=DISCORD_LINK_EXPIRE_MINUTES):
        discord_link_col.update_one(
            {"_id": req_doc["_id"]}, {"$set": {"status": "expired"}}
        )
        return _discord_link_page(
            "만료된 링크",
            "인증 링크가 만료되었습니다. 디스코드에서 인증 버튼을 다시 눌러주세요.",
            False,
        )

    users_db.update_one(
        {"uid": user["sub"]}, {"$set": {"discord_id": req_doc["discord_id"]}}
    )
    discord_link_col.update_one(
        {"_id": req_doc["_id"]},
        {"$set": {"status": "linked", "uid": user["sub"], "name": user.get("name")}},
    )

    return _discord_link_page(
        "인증 완료",
        f"{user.get('name')}님, knpu.re.kr 계정으로 인증되었습니다. 디스코드로 돌아가주세요.",
        True,
    )


@router.get("/manager")
def manager_redirect():
    return RedirectResponse(url="https://manager.knpu.re.kr", status_code=301)


@router.get("/manager/download")
def manager_download_page():
    return RedirectResponse(
        url="https://manager.knpu.re.kr/api/download", status_code=301
    )


# 매뉴얼은 각 서비스 서버 안으로 옮겼다 — 옛 북마크/링크가 죽지 않도록 새 위치로 리다이렉트만 남긴다.
@router.get("/manual/kemkim")
def manual_kemkim():
    return RedirectResponse(url="https://kemkim.knpu.re.kr/manual", status_code=301)


@router.get("/manual/network")
def manual_network():
    return RedirectResponse(url="https://network.knpu.re.kr/manual", status_code=301)


@router.get("/manual/hate_analysis")
def manual_hate_analysis():
    return RedirectResponse(
        url="https://manager.knpu.re.kr/manual/hate_analysis", status_code=301
    )


@router.get("/manual/whisper")
def manual_whisper():
    return RedirectResponse(
        url="https://manager.knpu.re.kr/manual/whisper", status_code=301
    )


@router.get("/manual/yolo")
def manual_yolo():
    return RedirectResponse(
        url="https://manager.knpu.re.kr/manual/yolo", status_code=301
    )


@router.get("/favicon.ico")
def favicon():
    return _page("assets/imgs/fpei_logo_favicon.ico")
