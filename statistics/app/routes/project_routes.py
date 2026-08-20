# app/routes/project_routes.py
import os

import requests
from fastapi import APIRouter, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from starlette.background import BackgroundTask

from app.services import project_store, analyze_service
from system import uploads as upload_staging
from app.db import user_logs_db
from system.logging.user_log import insert_log

router = APIRouter()

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
# 개발 중 자주 바뀌는 페이지라 브라우저가 옛 버전을 캐시해두는 일이 없도록 한다.
_NO_CACHE = {"Cache-Control": "no-store, must-revalidate"}


def _page(filename: str) -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, filename), headers=_NO_CACHE)


def _user(request: Request) -> dict:
    user = request.scope.get("state", {}).get("user")
    if not user:
        raise HTTPException(401, "인증이 필요합니다")
    return user


def _uid(request: Request) -> str:
    return _user(request)["uid"]


def _is_admin(request: Request) -> bool:
    return _user(request).get("role") == "admin"


def _handle_store_error(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except project_store.NotFound as e:
        raise HTTPException(404, str(e))
    except project_store.Forbidden as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/", response_class=HTMLResponse)
async def app_shell():
    return _page("viewer.html")


@router.get("/viewer", response_class=HTMLResponse)
async def app_shell_viewer():
    return _page("viewer.html")


@router.get("/manual", response_class=HTMLResponse)
async def manual_page():
    return _page("manual.html")


@router.get("/api/me")
async def api_me(request: Request):
    user = request.scope.get("state", {}).get("user")
    if not user:
        raise HTTPException(401, "인증이 필요합니다")
    return JSONResponse(user)


# ---------------------------------------------------------------------------
# 프로젝트 CRUD
# ---------------------------------------------------------------------------


@router.get("/api/projects")
async def api_list_projects(request: Request, all: bool = False):
    if all:
        if not _is_admin(request):
            raise HTTPException(403, "관리자만 전체 프로젝트를 볼 수 있습니다")
        return JSONResponse({"projects": project_store.list_all_projects()})
    return JSONResponse(
        {"projects": _handle_store_error(project_store.list_projects, _uid(request))}
    )


@router.post("/api/projects")
async def api_create_project(
    request: Request, file: UploadFile = File(...), name: str = Form(None)
):
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "통계분석 결과 zip 파일을 업로드해주세요.")
    content = await file.read()
    project_name = name or os.path.splitext(file.filename)[0]
    uid = _uid(request)
    project = _handle_store_error(
        project_store.create_project, uid, content, project_name
    )
    insert_log(
        user_logs_db,
        uid,
        "statistics.project.create",
        "statistics",
        target={
            "type": "project",
            "id": project["project_id"],
            "name": project["name"],
        },
    )
    return JSONResponse(project)


@router.post("/api/projects/upload-zip")
async def api_upload_zip_stage(request: Request, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "통계분석 결과 zip 파일을 업로드해주세요.")
    content = await file.read()
    stage_id = upload_staging.stage(_uid(request), content, file.filename)
    return JSONResponse(
        {"stage_id": stage_id, "suggested_name": os.path.splitext(file.filename)[0]}
    )


@router.post("/api/projects/finalize-zip")
async def api_finalize_zip(request: Request):
    body = await request.json()
    uid = _uid(request)
    try:
        content, filename = upload_staging.pop(uid, body.get("stage_id", ""))
    except ValueError as e:
        raise HTTPException(400, str(e))
    project_name = (body.get("name") or "").strip() or os.path.splitext(filename)[0]
    project = _handle_store_error(
        project_store.create_project, uid, content, project_name
    )
    insert_log(
        user_logs_db,
        uid,
        "statistics.project.create",
        "statistics",
        target={
            "type": "project",
            "id": project["project_id"],
            "name": project["name"],
        },
    )
    return JSONResponse(project)


@router.patch("/api/projects/{project_id}")
async def api_rename_project(project_id: str, request: Request):
    body = await request.json()
    uid = _uid(request)
    project = _handle_store_error(
        project_store.rename_project, uid, project_id, body.get("name", "")
    )
    insert_log(
        user_logs_db,
        uid,
        "statistics.project.rename",
        "statistics",
        target={"type": "project", "id": project_id, "name": project["name"]},
    )
    return JSONResponse(project)


@router.delete("/api/projects/{project_id}")
async def api_delete_project(project_id: str, request: Request):
    uid = _uid(request)
    project = _handle_store_error(project_store.get_project, uid, project_id)
    _handle_store_error(project_store.delete_project, uid, project_id)
    insert_log(
        user_logs_db,
        uid,
        "statistics.project.delete",
        "statistics",
        target={"type": "project", "id": project_id, "name": project.get("name")},
    )
    return JSONResponse({"message": "삭제되었습니다"})


@router.patch("/api/projects/{project_id}/folder")
async def api_move_project_folder(project_id: str, request: Request):
    body = await request.json()
    uid = _uid(request)
    project = _handle_store_error(
        project_store.move_project_folder, uid, project_id, body.get("folder_id")
    )
    insert_log(
        user_logs_db,
        uid,
        "statistics.project.move_folder",
        "statistics",
        target={"type": "project", "id": project_id, "name": project.get("name")},
        metadata={"folder_id": project.get("folder_id")},
    )
    return JSONResponse(project)


# ---------------------------------------------------------------------------
# 폴더 CRUD
# ---------------------------------------------------------------------------


@router.get("/api/folders")
async def api_list_folders(request: Request, all: bool = False):
    if all:
        if not _is_admin(request):
            raise HTTPException(403, "관리자만 전체 폴더를 볼 수 있습니다")
        return JSONResponse({"folders": project_store.list_all_folders()})
    return JSONResponse(
        {"folders": _handle_store_error(project_store.list_folders, _uid(request))}
    )


@router.post("/api/folders")
async def api_create_folder(request: Request):
    body = await request.json()
    uid = _uid(request)
    folder = _handle_store_error(project_store.create_folder, uid, body.get("name", ""))
    insert_log(
        user_logs_db,
        uid,
        "statistics.folder.create",
        "statistics",
        target={"type": "folder", "id": folder["folder_id"], "name": folder["name"]},
    )
    return JSONResponse(folder)


@router.patch("/api/folders/{folder_id}")
async def api_rename_folder(folder_id: str, request: Request):
    body = await request.json()
    uid = _uid(request)
    folder = _handle_store_error(
        project_store.rename_folder, uid, folder_id, body.get("name", "")
    )
    insert_log(
        user_logs_db,
        uid,
        "statistics.folder.rename",
        "statistics",
        target={"type": "folder", "id": folder_id, "name": folder["name"]},
    )
    return JSONResponse(folder)


@router.delete("/api/folders/{folder_id}")
async def api_delete_folder(folder_id: str, request: Request):
    uid = _uid(request)
    _handle_store_error(project_store.delete_folder, uid, folder_id)
    insert_log(
        user_logs_db,
        uid,
        "statistics.folder.delete",
        "statistics",
        target={"type": "folder", "id": folder_id},
    )
    return JSONResponse({"message": "삭제되었습니다"})


@router.get("/viewer/{project_id}", response_class=HTMLResponse)
async def viewer_page(project_id: str, request: Request):
    _handle_store_error(
        project_store.get_project, _uid(request), project_id, _is_admin(request)
    )
    return _page("viewer.html")


@router.get("/api/projects/{project_id}/meta")
async def project_meta(project_id: str, request: Request):
    return JSONResponse(
        _handle_store_error(
            project_store.get_project, _uid(request), project_id, _is_admin(request)
        )
    )


@router.get("/api/projects/{project_id}/download")
async def project_download(project_id: str, request: Request):
    uid = _uid(request)
    is_admin = _is_admin(request)
    zip_path = _handle_store_error(project_store.zip_raw, uid, project_id, is_admin)
    project = project_store.get_project(uid, project_id, is_admin)
    insert_log(
        user_logs_db,
        uid,
        "statistics.project.download",
        "statistics",
        target={"type": "project", "id": project_id, "name": project.get("name")},
    )
    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=f"{project['name']}.zip",
        background=BackgroundTask(os.remove, zip_path),
    )


# ---------------------------------------------------------------------------
# 분석 결과 조회 (표 + 설명 — 전부 한 번에)
# ---------------------------------------------------------------------------


@router.get("/api/projects/{project_id}/base")
async def project_base(project_id: str, request: Request):
    base = _handle_store_error(
        project_store.load_base, _uid(request), project_id, _is_admin(request)
    )
    return JSONResponse(base)


# ---------------------------------------------------------------------------
# 실행(분석): 원본 CSV 업로드 -> manager/server /analysis/statistics 호출
# ---------------------------------------------------------------------------


@router.get("/api/analyze/options")
async def analyze_options():
    return JSONResponse(
        {
            "platforms": analyze_service.PLATFORM_CATEGORIES,
            "common_category": analyze_service.COMMON_CATEGORY,
        }
    )


@router.get("/api/progress-config")
async def progress_config():
    return JSONResponse({"ws_url": analyze_service.PROGRESS_PUBLIC_WS_URL})


@router.get("/api/crawl-dbs")
async def api_crawl_dbs(request: Request, q: str = "", page: int = 1):
    session_token = request.cookies.get("session")
    if not session_token:
        raise HTTPException(401, "인증이 필요합니다")
    try:
        resp = requests.get(
            f"{analyze_service.CRAWLER_INTERNAL_API}/db-list",
            params={
                "status": "completed",
                "per_page": 30,
                "page": max(1, page),
                "q": q,
            },
            cookies={"session": session_token},
            timeout=15,
        )
    except requests.RequestException as e:
        raise HTTPException(502, f"크롤러 서버 요청 실패: {e}")
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, resp.text)
    return JSONResponse(resp.json())


@router.get("/api/crawl-dbs/{uid}/files")
async def api_crawl_db_files(uid: str, request: Request):
    session_token = request.cookies.get("session")
    if not session_token:
        raise HTTPException(401, "인증이 필요합니다")
    try:
        resp = requests.get(
            f"{analyze_service.CRAWLER_INTERNAL_API}/db-list/{uid}/files",
            cookies={"session": session_token},
            timeout=15,
        )
    except requests.RequestException as e:
        raise HTTPException(502, f"크롤러 서버 요청 실패: {e}")
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, resp.text)
    data = resp.json()
    data["files"] = [f for f in data.get("files", []) if f.get("type") == "raw"]
    return JSONResponse(data)


@router.post("/api/crawl-dbs/{uid}/select")
async def api_crawl_db_select(uid: str, request: Request):
    session_token = request.cookies.get("session")
    if not session_token:
        raise HTTPException(401, "인증이 필요합니다")
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "파일명이 필요합니다")

    try:
        resp = requests.get(
            f"{analyze_service.CRAWLER_INTERNAL_API}/db-list/{uid}/file",
            params={"name": name},
            cookies={"session": session_token},
            timeout=60,
        )
    except requests.RequestException as e:
        raise HTTPException(502, f"크롤러 서버 요청 실패: {e}")
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, resp.text)

    filename = name.rsplit(".", 1)[0] + ".csv"
    stage_id = upload_staging.stage(_uid(request), resp.content, filename)
    insert_log(
        user_logs_db,
        _uid(request),
        "statistics.project.import_from_crawl_db",
        "statistics",
        target={"type": "crawl_db", "id": uid, "name": name},
    )
    return JSONResponse(
        {"stage_id": stage_id, "suggested_name": os.path.splitext(filename)[0]}
    )


@router.post("/api/projects/analyze/upload")
async def api_analyze_upload_stage(request: Request, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "원본 CSV 파일을 업로드해주세요.")
    content = await file.read()
    stage_id = upload_staging.stage(_uid(request), content, file.filename)
    return JSONResponse(
        {"stage_id": stage_id, "suggested_name": os.path.splitext(file.filename)[0]}
    )


@router.post("/api/projects/analyze/start")
async def api_analyze_start(request: Request):
    uid = _uid(request)

    body = await request.json()
    try:
        content, filename = upload_staging.pop(uid, body.get("stage_id", ""))
    except ValueError as e:
        raise HTTPException(400, str(e))

    category = (body.get("category") or "").strip()
    platform = (body.get("platform") or "").strip()
    if not category or not platform:
        raise HTTPException(400, "분석 종류와 플랫폼을 선택해주세요.")

    project_name = (body.get("name") or "").strip() or os.path.splitext(filename)[0]
    try:
        pid = analyze_service.start_job(
            content,
            filename,
            category,
            platform,
            uid,
            project_name=project_name,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    insert_log(
        user_logs_db,
        uid,
        "statistics.project.analyze_start",
        "statistics",
        target={"type": "project", "id": pid, "name": project_name},
        metadata={"category": category, "platform": platform},
    )
    return JSONResponse({"pid": pid})


@router.get("/api/projects/analyze/{pid}/status")
async def api_analyze_status(pid: str, request: Request):
    _uid(request)
    return JSONResponse(analyze_service.get_job(pid))
