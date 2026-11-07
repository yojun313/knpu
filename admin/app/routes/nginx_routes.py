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
from app.services.nginx_service import HELPER_MISSING, NginxService
from app.services import domain_folder_service
from app.routes.dependencies import get_current_user
from app.services import settings_service
from app.db import user_logs_col, homepage_users_col
from app.libs.jwt import decode_token
from system.logging.user_log import insert_log
from system.auth.session import revalidate_session
from urllib.parse import urlsplit


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
    ok, message = NginxService.check_rename(
        payload.old_domain.strip().lower(), payload.new_domain.strip().lower()
    )
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": "변경 가능한 도메인입니다."}


def _invalid_console_input(action, data):
    """콘솔 값을 검증하고 정리한다. 헬퍼가 root 로 다시 검증하지만 먼저 이유를 알려 준다."""
    for key in ("domain", "new_domain"):
        if isinstance(data.get(key), str):
            data[key] = data[key].strip().lower()
    if isinstance(data.get("email"), str):
        data["email"] = data["email"].strip()
    domains = (
        [data.get("old_domain"), data.get("new_domain")]
        if action == "rename"
        else [data.get("domain")]
    )
    if not all(NginxService.is_valid_domain(d) for d in domains):
        return "유효하지 않은 도메인입니다."
    if action in ("add", "rename") and not NginxService.is_valid_email(
        data.get("email")
    ):
        return "유효하지 않은 이메일입니다."
    if action == "add":
        if not NginxService.is_valid_port(data.get("port")):
            return "유효하지 않은 포트입니다."
        path = NginxService.normalize_path(data.get("path") or "/")
        if path is None:
            return "유효하지 않은 경로입니다."
        data["path"] = path
    return None


@router.websocket("/ws/console")
async def nginx_console_ws(websocket: WebSocket):
    await websocket.accept()

    # 브라우저는 웹소켓에 CORS를 적용하지 않으므로, 다른 사이트에서 연 연결은 직접 막는다
    origin = urlsplit(websocket.headers.get("origin") or "").netloc
    if not origin or origin != websocket.headers.get("host"):
        await websocket.send_text("허용되지 않은 요청입니다")
        await websocket.close()
        return

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
        action = data.get("action") if isinstance(data, dict) else None
        if action not in ("add", "rename", "delete"):
            await websocket.send_text("Invalid Action")
            await websocket.close()
            return

        error = _invalid_console_input(action, data)
        if error:
            await websocket.send_text(f"에러 발생: {error}")
            await websocket.close()
            return

        if not NginxService.helper_installed():
            await websocket.send_text(f"에러 발생: {HELPER_MISSING}")
            await websocket.close()
            return

        if action == "add":
            args = ["add", data["domain"], data["email"], data["port"], data["path"]]
            insert_log(
                user_logs_col,
                admin_uid,
                "admin.nginx.cert_issue",
                "admin",
                message=f"SSL 인증서 발급 + nginx 등록: {data['domain']}",
                target={"type": "nginx_domain", "id": data["domain"]},
                metadata={"port": data["port"], "path": data["path"]},
            )
        elif action == "rename":
            old_domain = data["old_domain"]
            new_domain = data["new_domain"]
            ok, message = NginxService.check_rename(old_domain, new_domain)
            if not ok:
                await websocket.send_text(f"에러 발생: {message}")
                await websocket.close()
                return
            args = ["rename", old_domain, new_domain, data["email"]]
            insert_log(
                user_logs_col,
                admin_uid,
                "admin.nginx.domain_rename",
                "admin",
                message=f"도메인 이름 변경: {old_domain} -> {new_domain}",
                target={"type": "nginx_domain", "id": new_domain},
                metadata={"old_domain": old_domain},
            )
        else:
            args = ["delete", data["domain"]]
            insert_log(
                user_logs_col,
                admin_uid,
                "admin.nginx.cert_delete",
                "admin",
                message=f"SSL 인증서 및 nginx 설정 삭제: {data['domain']}",
                target={"type": "nginx_domain", "id": data["domain"]},
            )

        process = await asyncio.create_subprocess_exec(
            *NginxService.helper_command(*args),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            limit=1024 * 1024,
        )

        # 브라우저가 끊겨도 헬퍼는 끝까지 돌리고 결과를 폴더에 반영한다
        connected = True
        while line := await process.stdout.readline():
            if connected:
                try:
                    await websocket.send_text(line.decode("utf-8", "replace").strip())
                except (WebSocketDisconnect, RuntimeError):
                    connected = False

        await process.wait()
        succeeded = process.returncode == 0
        notice = ""
        if succeeded and action == "add" and data.get("folder_id"):
            # 추가 모달에서 폴더를 골랐으면 생성 성공 직후 바로 그 폴더로 분류한다
            ok, _msg = domain_folder_service.assign_domain(
                data["domain"], data["folder_id"]
            )
            if ok:
                notice = "도메인을 선택한 폴더로 분류했습니다."
        if succeeded and action == "rename":
            domain_folder_service.rename_domain(data["old_domain"], data["new_domain"])
            notice = "폴더 소속을 새 도메인으로 옮겼습니다."
        if connected:
            if notice:
                await websocket.send_text(notice)
            await websocket.send_text(
                "작업이 완료되었습니다." if succeeded else "작업이 실패했습니다."
            )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(f"에러 발생: {str(e)}")
        except (WebSocketDisconnect, RuntimeError):
            pass
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass
