from fastapi import APIRouter
from fastapi.responses import FileResponse
import os

router = APIRouter()

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "format")

@router.get("/engkor")
def download_engkor_list():
    file_path = os.path.join(DATA_DIR, "engkor_list.csv")
    return FileResponse(
        file_path,
        media_type="text/csv",
        filename="engkor_list.csv"
    )

@router.post("/exception")
def download_exception_list():
    file_path = os.path.join(DATA_DIR, "exception_list.csv")
    return FileResponse(
        file_path,
        media_type="text/csv",
        filename="exception_list.csv"
    )

@router.get("/tokenize")
def download_tokenize_list():
    file_path = os.path.join(DATA_DIR, "tokenize_list.csv")
    return FileResponse(
        file_path,
        media_type="text/csv",
        filename="tokenize_list.csv"
    )
