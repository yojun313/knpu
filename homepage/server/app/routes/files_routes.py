from urllib.parse import quote
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.libs.manager_r2 import list_files, download_url

router = APIRouter()


@router.get("/files")
def get_files():
    try:
        return list_files()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve file list: {e}")


@router.get("/download/{filename}")
def download_file(filename: str):
    return RedirectResponse(url=download_url(quote(filename)))
