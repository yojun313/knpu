import os
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, RedirectResponse

from app.auth.dependencies import get_current_user_optional

router = APIRouter()

PUBLIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")


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


@router.get("/manager")
def manager_redirect():
    return RedirectResponse(url="https://manager.knpu.re.kr", status_code=301)


@router.get("/manager/download")
def manager_download_page():
    return _page("manager_download.html")


@router.get("/manual/kemkim")
def manual_kemkim():
    return _page("manuals/manual_kemkim.html")


@router.get("/manual/hate_analysis")
def manual_hate_analysis():
    return _page("manuals/manual_hateanalysis.html")


@router.get("/manual/whisper")
def manual_whisper():
    return _page("manuals/manual_whisper.html")


@router.get("/manual/yolo")
def manual_yolo():
    return _page("manuals/manual_detection.html")


@router.get("/manual/network")
def manual_network():
    return _page("manuals/manual_network.html")


@router.get("/favicon.ico")
def favicon():
    return _page("assets/imgs/fpei_logo_favicon.ico")
