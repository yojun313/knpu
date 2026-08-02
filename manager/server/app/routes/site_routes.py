import os
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

PUBLIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")


@router.get("/")
def manager_intro_page():
    return FileResponse(os.path.join(PUBLIC_DIR, "manager.html"))
