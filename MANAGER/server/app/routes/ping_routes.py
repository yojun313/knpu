# app/routers/ping_router.py
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/")
def ping():
    return JSONResponse(status_code=200, content={"message": "pong"})