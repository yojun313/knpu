import asyncio
from fastapi import (
    APIRouter,
    Request,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from app.services.nginx_service import NginxService
from app.services import domain_folder_service
from app.routes.dependencies import get_current_user
from app.services import settings_service
from app.db import user_logs_col, homepage_users_col
from app.libs.jwt import decode_token
from system.logging.user_log import insert_log
from system.auth.session import revalidate_session
import os


class PathAddRequest(BaseModel):
    domain: str
    path: str
    port: str


class PathEditRequest(BaseModel):
    domain: str
    path: str
    port: str


class PathDeleteRequest(BaseModel):
    domain: str
    path: str


class FolderCreateRequest(BaseModel):
    name: str


class FolderRenameRequest(BaseModel):
    name: str


class FolderAssignRequest(BaseModel):
    domain: str
    folder_id: str | None = None


router = APIRouter(prefix="/nginx", tags=["nginx"])
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["get_nav_items"] = settings_service.get_nav_items_ordered


@router.get("/")
async def nginx_manager_page(request: Request, user=Depends(get_current_user)):
    domains = NginxService.get_domains()
    return templates.TemplateResponse(
        request=request,
        name="nginx.html",
        context={
            "domains": domains,
            "groups": domain_folder_service.group_domains(domains),
            "folders": domain_folder_service.list_folders(),
            "active_page": "nginx",
        },
    )


# ---------- 표시용 폴더 (nginx 설정은 건드리지 않는다) ----------


@router.post("/folders")
async def create_folder(payload: FolderCreateRequest, user=Depends(get_current_user)):
    ok, message, folder = domain_folder_service.create_folder(payload.name)
    insert_log(
        user_logs_col,
        user["sub"],
        "admin.nginx.folder_create",
        "admin",
        message=f"도메인 폴더 생성: {payload.name}",
        target={"type": "nginx_folder", "id": (folder or {}).get("id")},
        outcome="success" if ok else "failure",
    )
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message, "folder": folder}


@router.put("/folders/{folder_id}")
async def rename_folder(
    folder_id: str, payload: FolderRenameRequest, user=Depends(get_current_user)
):
    ok, message = domain_folder_service.rename_folder(folder_id, payload.name)
    insert_log(
        user_logs_col,
        user["sub"],
        "admin.nginx.folder_rename",
        "admin",
        message=f"도메인 폴더 이름 변경: {payload.name}",
        target={"type": "nginx_folder", "id": folder_id},
        outcome="success" if ok else "failure",
    )
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@router.delete("/folders/{folder_id}")
async def delete_folder(folder_id: str, user=Depends(get_current_user)):
    ok, message = domain_folder_service.delete_folder(folder_id)
    insert_log(
        user_logs_col,
        user["sub"],
        "admin.nginx.folder_delete",
        "admin",
        message="도메인 폴더 삭제",
        target={"type": "nginx_folder", "id": folder_id},
        outcome="success" if ok else "failure",
    )
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@router.post("/folders/assign")
async def assign_domain_to_folder(
    payload: FolderAssignRequest, user=Depends(get_current_user)
):
    ok, message = domain_folder_service.assign_domain(payload.domain, payload.folder_id)
    insert_log(
        user_logs_col,
        user["sub"],
        "admin.nginx.folder_assign",
        "admin",
        message=f"도메인 폴더 이동: {payload.domain}",
        target={"type": "nginx_domain", "id": payload.domain},
        metadata={"folder_id": payload.folder_id},
        outcome="success" if ok else "failure",
    )
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@router.post("/paths/add")
async def add_path(payload: PathAddRequest, user=Depends(get_current_user)):
    ok, message = NginxService.add_path(payload.domain, payload.path, payload.port)
    insert_log(
        user_logs_col,
        user["sub"],
        "admin.nginx.path_add",
        "admin",
        message=f"nginx path 추가: {payload.domain}{payload.path} -> :{payload.port}",
        target={"type": "nginx_domain", "id": payload.domain},
        outcome="success" if ok else "failure",
    )
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@router.put("/paths/edit")
async def edit_path(payload: PathEditRequest, user=Depends(get_current_user)):
    ok, message = NginxService.edit_path_port(
        payload.domain, payload.path, payload.port
    )
    insert_log(
        user_logs_col,
        user["sub"],
        "admin.nginx.path_edit",
        "admin",
        message=f"nginx path 수정: {payload.domain}{payload.path} -> :{payload.port}",
        target={"type": "nginx_domain", "id": payload.domain},
        outcome="success" if ok else "failure",
    )
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@router.post("/paths/delete")
async def delete_path(payload: PathDeleteRequest, user=Depends(get_current_user)):
    ok, message, requires_full_delete = NginxService.delete_path(
        payload.domain, payload.path
    )
    insert_log(
        user_logs_col,
        user["sub"],
        "admin.nginx.path_delete",
        "admin",
        message=f"nginx path 삭제: {payload.domain}{payload.path}",
        target={"type": "nginx_domain", "id": payload.domain},
        outcome="success" if ok else "failure",
    )
    if requires_full_delete:
        return {"success": False, "requires_full_delete": True, "message": message}
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@router.websocket("/ws/console")
async def nginx_console_ws(websocket: WebSocket):
    await websocket.accept()

    token = websocket.cookies.get("session")
    payload = decode_token(token) if token else None
    live = revalidate_session(payload, homepage_users_col)
    if not live or live.get("role") != "admin":
        await websocket.send_text("인증이 필요합니다")
        await websocket.close()
        return
    admin_uid = live.get("sub")

    try:
        data = await websocket.receive_json()
        action = data.get("action")

        if action == "add":
            cmd = [
                "sudo",
                "bash",
                os.path.join(
                    os.path.abspath(
                        os.path.join(os.path.dirname(__file__), "..", "scripts")
                    ),
                    "add_nginx.sh",
                ),
                data["domain"],
                data["email"],
                data["port"],
                data.get("path") or "/",
            ]
            insert_log(
                user_logs_col,
                admin_uid,
                "admin.nginx.cert_issue",
                "admin",
                message=f"SSL 인증서 발급 + nginx 등록: {data['domain']}",
                target={"type": "nginx_domain", "id": data["domain"]},
                metadata={"port": data["port"], "path": data.get("path") or "/"},
            )
        elif action == "delete":
            cmd = [
                "sudo",
                "certbot",
                "delete",
                "--cert-name",
                data["domain"],
                "--non-interactive",
            ]
            insert_log(
                user_logs_col,
                admin_uid,
                "admin.nginx.cert_delete",
                "admin",
                message=f"SSL 인증서 및 nginx 설정 삭제: {data['domain']}",
                target={"type": "nginx_domain", "id": data["domain"]},
            )
        else:
            await websocket.send_text("Invalid Action")
            await websocket.close()
            return

        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )

        while True:
            line = await process.stdout.readline()
            if not line:
                break
            await websocket.send_text(line.decode().strip())

        await process.wait()
        if action == "delete":
            os.system(f"sudo rm -f /etc/nginx/sites-enabled/{data['domain']}")
            os.system(f"sudo rm -f /etc/nginx/sites-available/{data['domain']}")
            os.system("sudo systemctl reload nginx")
            await websocket.send_text("Nginx configuration removed and reloaded.")

        await websocket.send_text("작업이 완료되었습니다.")

    except Exception as e:
        await websocket.send_text(f"에러 발생: {str(e)}")
    finally:
        await websocket.close()
