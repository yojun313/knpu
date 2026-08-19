import requests
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from app.services.data_service import get_all_users, get_pending_users
from app.routes.dependencies import get_current_user
from app.services import settings_service
from system.endpoints import internal_api

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["get_nav_items"] = settings_service.get_nav_items_ordered

# 같은 장비의 홈페이지를 직접 부른다 — 공개 도메인(prod 고정)으로 나가면 dev
# 대시보드가 운영 홈페이지를 호출하게 되고, 불필요하게 nginx/TLS를 왕복한다.
# (같은 앱의 version_routes.py가 이미 쓰는 방식과 맞춤)
HOMEPAGE_AUTH_API = f"{internal_api('homepage')}/auth"


@router.get("/users")
async def read_users(request: Request, user=Depends(get_current_user)):
    users = get_all_users()
    pending_users = get_pending_users()
    return templates.TemplateResponse(
        request=request,
        name="users.html",
        context={
            "users": users,
            "pending_users": pending_users,
            "active_page": "users",
            "my_uid": user.get("sub"),
        },
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


@router.post("/users/{uid}/role")
async def change_user_role(uid: str, request: Request, user=Depends(get_current_user)):
    token = request.cookies.get("session")
    body = await request.json()
    res = requests.post(
        f"{HOMEPAGE_AUTH_API}/admin/users/{uid}/role",
        json={"role": body.get("role")},
        headers={"Authorization": f"Bearer {token}"},
    )
    return JSONResponse(status_code=res.status_code, content=res.json())


@router.delete("/users/{uid}")
async def delete_user(uid: str, request: Request, user=Depends(get_current_user)):
    token = request.cookies.get("session")
    res = requests.delete(
        f"{HOMEPAGE_AUTH_API}/admin/users/{uid}",
        headers={"Authorization": f"Bearer {token}"},
    )
    return JSONResponse(status_code=res.status_code, content=res.json())
