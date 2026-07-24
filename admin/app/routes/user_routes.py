import requests
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from app.services.data_service import get_all_users, get_pending_users
from app.routes.dependencies import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

HOMEPAGE_AUTH_API = "https://knpu.re.kr/api/auth"


@router.get("/users")
async def read_users(request: Request, user=Depends(get_current_user)):
    users = get_all_users()
    pending_users = get_pending_users()
    return templates.TemplateResponse(
        request=request,
        name="users.html",
        context={"users": users, "pending_users": pending_users, "active_page": "users"},
    )


@router.post("/users/{uid}/approve")
async def approve_user(uid: str, request: Request, user=Depends(get_current_user)):
    token = request.cookies.get("session")
    res = requests.post(
        f"{HOMEPAGE_AUTH_API}/admin/requests/{uid}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    return JSONResponse(status_code=res.status_code, content=res.json())


@router.post("/users/{uid}/reject")
async def reject_user(uid: str, request: Request, user=Depends(get_current_user)):
    token = request.cookies.get("session")
    res = requests.post(
        f"{HOMEPAGE_AUTH_API}/admin/requests/{uid}/reject",
        headers={"Authorization": f"Bearer {token}"},
    )
    return JSONResponse(status_code=res.status_code, content=res.json())
