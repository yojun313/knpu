from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app.libs.session import get_session, attach_session_cookie
from app.routes.complaint_routes import generate_complaints

PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"

router = APIRouter()


@router.get("/")
def index():
    return FileResponse(PUBLIC_DIR / "first_page.html")


@router.get("/basic_info")
def basic_info():
    return FileResponse(PUBLIC_DIR / "forms" / "basic_info.html")


@router.post("/submit")
async def submit(request: Request):
    form_data = dict(await request.form())
    redirect_page_name = form_data.get("고소 죄명")
    sid, session = get_session(request)

    if redirect_page_name:
        session["first_formData"] = form_data
        response = RedirectResponse(
            url=f"/forms/{redirect_page_name}.html", status_code=303
        )
    else:
        response = RedirectResponse(url="/error", status_code=303)

    attach_session_cookie(response, sid)
    return response


@router.post("/loading")
async def loading(request: Request):
    form_data = dict(await request.form())
    sid, session = get_session(request)

    if form_data:
        session["second_formData"] = form_data

    response = FileResponse(PUBLIC_DIR / "loading.html")
    attach_session_cookie(response, sid)
    return response


@router.get("/llm")
def llm(request: Request):
    sid, session = get_session(request)

    combined_data = {
        "first_formData": session.get("first_formData"),
        "second_formData": session.get("second_formData"),
    }

    try:
        result = generate_complaints({"combined_data": combined_data})
    except Exception:
        response = FileResponse(PUBLIC_DIR / "llm_failed.html")
        attach_session_cookie(response, sid)
        return response

    session["file_id"] = result["file_id"]
    session["preview_pdf"] = result["preview_pdf"]
    session["download_word"] = result["download_word"]
    session["download_pdf"] = result["download_pdf"]
    session["model_name"] = result["model_name"]
    session["model_url"] = result["model_url"]

    html = (PUBLIC_DIR / "result_page.html").read_text(encoding="utf-8")
    modified_html = (
        html.replace("pdf_url", f"/api{session['preview_pdf']}")
        .replace("word_download_url", f"/api{session['download_word']}")
        .replace("pdf_download_url", f"/api{session['download_pdf']}")
        .replace("MODEL_NAME", session["model_name"])
        .replace("MODEL_URL", session["model_url"])
    )

    response = HTMLResponse(modified_html)
    attach_session_cookie(response, sid)
    return response
