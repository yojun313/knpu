import os
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from app.libs import manager_r2

router = APIRouter()

PUBLIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")


@router.get("")
def download_page():
    return FileResponse(os.path.join(PUBLIC_DIR, "download.html"))


@router.get("/files")
def get_files():
    try:
        return manager_r2.list_files()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve file list: {e}"
        )


@router.get("/file/{filename}")
def download_file(filename: str):
    return RedirectResponse(url=manager_r2.download_url(quote(filename)))
