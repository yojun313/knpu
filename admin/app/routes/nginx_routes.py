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


class DomainRenameRequest(BaseModel):
    old_domain: str
    new_domain: str


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


@router.post("/domains/rename/check")
async def check_rename_domain(
    payload: DomainRenameRequest, user=Depends(get_current_user)
):
    """콘솔을 열기 전에 미리 검증한다. 실제 변경은 웹소켓 rename 액션이 수행한다."""
    ok, message = NginxService.build_renamed_config(
        payload.old_domain, payload.new_domain
    )
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": "변경 가능한 도메인입니다."}


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
        rename_stdin = None

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
        elif action == "rename":
            old_domain = data["old_domain"]
            new_domain = data["new_domain"]
            ok, result = NginxService.build_renamed_config(old_domain, new_domain)
            if not ok:
                await websocket.send_text(f"에러 발생: {result}")
                await websocket.close()
                return
            rename_stdin = result
            cmd = [
                "sudo",
                "bash",
                os.path.join(
                    os.path.abspath(
                        os.path.join(os.path.dirname(__file__), "..", "scripts")
                    ),
                    "rename_nginx.sh",
                ),
                old_domain,
                new_domain,
                data["email"],
            ]
            insert_log(
                user_logs_col,
                admin_uid,
                "admin.nginx.domain_rename",
                "admin",
                message=f"도메인 이름 변경: {old_domain} -> {new_domain}",
                target={"type": "nginx_domain", "id": new_domain},
                metadata={"old_domain": old_domain},
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
            *cmd,
            stdin=asyncio.subprocess.PIPE if rename_stdin else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        if rename_stdin:
            process.stdin.write(rename_stdin.encode())
            await process.stdin.drain()
            process.stdin.close()

        while True:
            line = await process.stdout.readline()
            if not line:
                break
            await websocket.send_text(line.decode().strip())

        await process.wait()
        if action == "add" and process.returncode == 0 and data.get("folder_id"):
            # 추가 모달에서 폴더를 골랐으면 생성 성공 직후 바로 그 폴더로 분류한다
            ok, _msg = domain_folder_service.assign_domain(
                data["domain"], data["folder_id"]
            )
            if ok:
                await websocket.send_text("도메인을 선택한 폴더로 분류했습니다.")
        if action == "rename" and process.returncode == 0:
            domain_folder_service.rename_domain(data["old_domain"], data["new_domain"])
            await websocket.send_text("폴더 소속을 새 도메인으로 옮겼습니다.")
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
