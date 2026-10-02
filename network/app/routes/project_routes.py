# app/routes/project_routes.py
import asyncio
import os
import io

import pandas as pd
import requests
from fastapi import APIRouter, UploadFile, File, Form, Query, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse, Response

from app.services import (
    project_store,
    graph_analysis,
    analyze_service,
    network_ai,
    network_ai_jobs,
)
from system import uploads as upload_staging
from system.jobs import submit as submit_job
from system.jobs.routes import parse_schedule, status_compat as job_status_compat
from app.db import user_logs_db
from system.logging.user_log import insert_log


def _parse_csv_header(content: bytes) -> list[str]:
    try:
        first_line = content.split(b"\n", 1)[0].decode("utf-8-sig", errors="ignore")
    except Exception:
        return []
    return [c.strip().strip('"') for c in first_line.split(",") if c.strip()]


def _check_source_csv(content: bytes):
    if len(content) > 250 * 1024 * 1024:
        raise HTTPException(413, "원본 CSV는 250MB 이하로 업로드해주세요.")
    try:
        columns = pd.read_csv(
            io.BytesIO(content), nrows=0, encoding="utf-8-sig"
        ).columns
    except Exception:
        raise HTTPException(400, "UTF-8 CSV 파일을 읽지 못했습니다.")
    names = {str(c).strip().lower() for c in columns}
    if not names & {
        "article text",
        "content",
        "body",
        "text",
        "article",
        "본문",
        "기사본문",
        "원문",
    }:
        raise HTTPException(
            400, "원문 열(Article Text, Content, Text 등)이 있는 CSV가 필요합니다."
        )


router = APIRouter()

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
MAX_EDGES_DEFAULT = 4000
# 개발 중 자주 바뀌는 페이지라 브라우저가 옛 버전을 캐시해두는 일이 없도록 한다.
_NO_CACHE = {"Cache-Control": "no-store, must-revalidate"}


def _page(filename: str) -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, filename), headers=_NO_CACHE)


def _user(request: Request) -> dict:
    user = request.scope.get("state", {}).get("user")
    if not user:
        # 미들웨어가 이미 /api/* 는 401로 막아주므로 정상 흐름에서는 도달하지 않는다.
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
        raise HTTPException(400, "네트워크 분석 결과 zip 파일을 업로드해주세요.")
    content = await file.read()
    project_name = name or os.path.splitext(file.filename)[0]
    uid = _uid(request)
    project = _handle_store_error(
        project_store.create_project, uid, content, project_name
    )
    insert_log(
        user_logs_db,
        uid,
        "network.project.create",
        "network",
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
        raise HTTPException(400, "네트워크 분석 결과 zip 파일을 업로드해주세요.")
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
        "network.project.create",
        "network",
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
        "network.project.rename",
        "network",
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
        "network.project.delete",
        "network",
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
        "network.project.move_folder",
        "network",
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
        "network.folder.create",
        "network",
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
        "network.folder.rename",
        "network",
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
        "network.folder.delete",
        "network",
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


@router.get("/api/projects/{project_id}/summary")
async def project_summary(project_id: str, request: Request, tag: str = Query("")):
    graph = _handle_store_error(
        project_store.load_graph, _uid(request), project_id, tag, _is_admin(request)
    )
    summary = graph_analysis.compute_summary(graph)
    summary["community_keywords"] = graph_analysis.compute_community_keywords(graph)
    summary["tag"] = graph["tag"]
    summary["label"] = graph["label"]
    return JSONResponse(summary)


@router.get("/api/projects/{project_id}/data")
async def project_data(
    project_id: str,
    request: Request,
    tag: str = Query(""),
    full: bool = Query(False),
    max_edges: int = Query(MAX_EDGES_DEFAULT),
):
    graph = _handle_store_error(
        project_store.load_graph, _uid(request), project_id, tag, _is_admin(request)
    )

    edges = graph["edges"]
    truncated = False
    if not full and len(edges) > max_edges:
        edges = sorted(edges, key=lambda e: e["weight"], reverse=True)[:max_edges]
        truncated = True

    return JSONResponse(
        {
            "tag": graph["tag"],
            "label": graph["label"],
            "has_community": graph["has_community"],
            "has_layout": graph["has_layout"],
            "metric_keys": graph["metric_keys"],
            "nodes": graph["nodes"],
            "edges": edges,
            "truncated": truncated,
            "total_edges": len(graph["edges"]),
        }
    )


@router.post("/api/projects/{project_id}/ai-analysis")
async def project_ai_analysis(project_id: str, request: Request):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(400, "분석 요청 형식이 올바르지 않습니다.")
    mode = str(payload.get("mode") or "overview")
    if mode not in ("overview", "word", "pair", "community"):
        raise HTTPException(400, "분석 범위가 올바르지 않습니다.")
    tag = str(payload.get("tag") or "")
    word = str(payload.get("word") or "").strip()
    other = str(payload.get("other") or "").strip()
    try:
        community = int(payload.get("community")) if mode == "community" else None
    except (TypeError, ValueError):
        raise HTTPException(400, "커뮤니티를 선택해주세요.")
    if mode in ("word", "pair") and not word:
        raise HTTPException(400, "분석할 단어를 선택해주세요.")
    if mode == "pair" and (not other or other == word):
        raise HTTPException(400, "서로 다른 두 단어를 선택해주세요.")
    uid, admin = _uid(request), _is_admin(request)
    _handle_store_error(project_store.get_project, uid, project_id, admin)
    normalized = {
        "mode": mode,
        "tag": tag,
        "word": word,
        "other": other,
        "community": community,
    }
    job_id = network_ai_jobs.start_job(uid, project_id, normalized, admin)
    return JSONResponse({"job_id": job_id, "status": "running"}, status_code=202)


@router.get("/api/projects/{project_id}/ai-analysis/{job_id}")
async def project_ai_analysis_status(project_id: str, job_id: str, request: Request):
    return JSONResponse(
        _handle_store_error(network_ai_jobs.get_job, _uid(request), project_id, job_id)
    )


@router.get("/api/ai-jobs/active")
async def active_ai_jobs(request: Request):
    return JSONResponse({"jobs": network_ai_jobs.active_jobs(_uid(request))})


@router.get("/api/projects/{project_id}/ai-reports")
async def project_ai_reports(project_id: str, request: Request):
    reports = _handle_store_error(
        project_store.list_ai_reports, _uid(request), project_id, _is_admin(request)
    )
    return JSONResponse({"reports": reports})


@router.get("/api/projects/{project_id}/ai-reports/{report_id}")
async def project_ai_report(project_id: str, report_id: str, request: Request):
    saved = _handle_store_error(
        project_store.load_ai_report,
        _uid(request),
        project_id,
        report_id,
        _is_admin(request),
    )
    return JSONResponse(saved)


@router.get("/api/projects/{project_id}/ai-reports/{report_id}/export")
async def project_ai_report_export(project_id: str, report_id: str, request: Request):
    uid = _uid(request)
    saved = _handle_store_error(
        project_store.load_ai_report, uid, project_id, report_id, _is_admin(request)
    )
    insert_log(
        user_logs_db,
        uid,
        "network.ai_report.export",
        "network",
        target={"type": "project", "id": project_id},
        metadata={"report_id": report_id},
    )
    return Response(
        content=network_ai.markdown_report(saved).encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="network_report_{report_id}.md"'
        },
    )


@router.post("/api/projects/{project_id}/source")
async def project_upload_source(
    project_id: str, request: Request, file: UploadFile = File(...)
):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "원문 CSV 파일을 업로드해주세요.")
    content = await file.read()
    _check_source_csv(content)
    uid = _uid(request)
    _handle_store_error(project_store.save_source_csv, uid, project_id, content)
    insert_log(
        user_logs_db,
        uid,
        "network.project.source_upload",
        "network",
        target={"type": "project", "id": project_id},
        metadata={"filename": file.filename},
    )
    return JSONResponse({"message": "원문 CSV가 저장되었습니다."})


@router.post("/api/projects/{project_id}/source/from-crawl-db")
async def project_source_from_crawl_db(project_id: str, request: Request):
    uid = _uid(request)
    _handle_store_error(project_store.get_project, uid, project_id)
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(401, "인증이 필요합니다.")
    body = await request.json()
    crawl_uid = str(body.get("uid") or "").strip()
    name = str(body.get("name") or "").strip()
    if (
        not crawl_uid
        or os.path.basename(name) != name
        or not name.endswith(".parquet")
        or name.startswith("token_")
    ):
        raise HTTPException(400, "크롤링 DB의 원본 파일을 선택해주세요.")
    try:
        response = requests.get(
            f"{analyze_service.CRAWLER_INTERNAL_API}/db-list/{crawl_uid}/file",
            params={"name": name},
            cookies={"session": token},
            timeout=90,
        )
    except requests.RequestException as exc:
        raise HTTPException(502, f"크롤러 서버 요청 실패: {exc}")
    if response.status_code != 200:
        raise HTTPException(response.status_code, response.text)
    _check_source_csv(response.content)
    source_ref = {
        "uid": crawl_uid,
        "name": name,
        "db_name": str(body.get("db_name") or "")[:300],
    }
    _handle_store_error(
        project_store.save_source_csv, uid, project_id, response.content, source_ref
    )
    insert_log(
        user_logs_db,
        uid,
        "network.project.source_from_crawl_db",
        "network",
        target={"type": "project", "id": project_id},
        metadata={"crawl_uid": crawl_uid, "name": name},
    )
    return JSONResponse(
        {"message": "크롤링 DB 원문을 첨부했습니다.", "source_ref": source_ref}
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
async def api_crawl_db_files(uid: str, request: Request, kind: str = "token"):
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
    if kind not in ("token", "raw"):
        raise HTTPException(400, "파일 종류가 올바르지 않습니다.")
    data["files"] = [f for f in data.get("files", []) if f.get("type") == kind]
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
        "network.project.import_from_crawl_db",
        "network",
        target={"type": "crawl_db", "id": uid, "name": name},
    )
    return JSONResponse(
        {
            "stage_id": stage_id,
            "suggested_name": os.path.splitext(filename)[0],
            "columns": _parse_csv_header(resp.content),
        }
    )


@router.post("/api/projects/analyze/upload")
async def api_analyze_upload_stage(request: Request, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "토큰화된 CSV 파일을 업로드해주세요.")
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

    built_option = analyze_service.build_option(body.get("option") or {})
    if not built_option.get("text_col"):
        raise HTTPException(400, "분석할 열(대상 열)을 선택해주세요.")

    project_name = (body.get("name") or "").strip() or os.path.splitext(filename)[0]
    scheduled = parse_schedule(body.get("scheduled_at"))
    job = await asyncio.to_thread(
        submit_job,
        service="network",
        kind="network",
        kind_label="네트워크 분석",
        user=_user(request),
        title=project_name,
        params=built_option,
        content=content,
        filename=filename,
        scheduled_ts=scheduled,
    )
    insert_log(
        user_logs_db,
        uid,
        "network.project.analyze_start",
        "network",
        target={"type": "job", "id": job["_id"], "name": project_name},
        metadata={
            "text_col": built_option.get("text_col"),
            "scheduled_ts": job.get("scheduled_ts"),
        },
    )
    return JSONResponse(
        {"pid": job["_id"], "job_id": job["_id"], "status": job["status"]}
    )


@router.get("/api/projects/analyze/{pid}/status")
async def api_analyze_status(pid: str, request: Request):
    return JSONResponse(job_status_compat(_uid(request), pid))
