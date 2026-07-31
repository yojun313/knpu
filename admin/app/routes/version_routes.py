import os
import requests
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from app.routes.dependencies import get_current_user
from app.services import settings_service

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["get_nav_items"] = settings_service.get_nav_items_ordered

# manager_server가 admin과 같은 서버에서 돌아가므로 내부 호출은 로컬호스트로 바로 붙는다
# (다른 서비스들의 discord_notify.py 프록시와 동일한 관례).
MANAGER_SERVER_API = os.getenv(
    "MANAGER_SERVER_INTERNAL_API", "http://localhost:8000/api"
)


def _auth_header(request: Request) -> dict:
    token = request.cookies.get("session")
    return {"Authorization": f"Bearer {token}"} if token else {}


@router.get("/versions")
async def versions_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse(
        request=request, name="versions.html", context={"active_page": "versions"}
    )


@router.get("/api/versions")
async def api_list_versions(request: Request, user=Depends(get_current_user)):
    res = requests.get(
        f"{MANAGER_SERVER_API}/board/version", headers=_auth_header(request)
    )
    if not res.ok:
        raise HTTPException(
            status_code=res.status_code, detail="버전 목록을 불러오지 못했습니다"
        )
    return res.json()


@router.post("/api/versions")
async def api_add_version(
    request: Request,
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    res = requests.post(
        f"{MANAGER_SERVER_API}/board/version/add",
        json=payload,
        headers=_auth_header(request),
    )
    if not res.ok:
        raise HTTPException(status_code=res.status_code, detail=_extract_detail(res))
    return res.json()


@router.put("/api/versions/{version_name}")
async def api_edit_version(
    version_name: str,
    request: Request,
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    res = requests.put(
        f"{MANAGER_SERVER_API}/board/version/{version_name}",
        json=payload,
        headers=_auth_header(request),
    )
    if not res.ok:
        raise HTTPException(status_code=res.status_code, detail=_extract_detail(res))
    return res.json()


@router.delete("/api/versions/{version_name}")
async def api_delete_version(
    version_name: str, request: Request, user=Depends(get_current_user)
):
    res = requests.delete(
        f"{MANAGER_SERVER_API}/board/version/{version_name}",
        headers=_auth_header(request),
    )
    if not res.ok:
        raise HTTPException(status_code=res.status_code, detail=_extract_detail(res))
    return res.json()


def _extract_detail(res: requests.Response) -> str:
    try:
        return (
            res.json().get("detail")
            or res.json().get("message")
            or "요청이 실패했습니다"
        )
    except Exception:
        return "요청이 실패했습니다"
