import csv
import io
import os
import uuid

import requests
from fastapi import APIRouter, UploadFile, File, Form, Query, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse, Response
from starlette.background import BackgroundTask

from app.services import (
    project_store,
    kemkim_analysis,
    analyze_service,
)
from system import uploads as upload_staging
from app.db import user_logs_db
from system.logging.user_log import insert_log

router = APIRouter()


def _suggest_date_range(filename: str) -> tuple[str | None, str | None]:
    parts = os.path.splitext(filename)[0].split("_")
    if len(parts) < 5:
        return None, None
    try:
        start_raw, end_raw = parts[3], parts[4]
        from datetime import datetime as _dt

        start = _dt.strptime(start_raw, "%Y%m%d").strftime("%Y-%m-%d")
        end = _dt.strptime(end_raw, "%Y%m%d").strftime("%Y-%m-%d")
        return start, end
    except ValueError:
        return None, None


STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
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
        raise HTTPException(400, "KEMKIM 분석 결과 zip 파일을 업로드해주세요.")
    content = await file.read()
    project_name = name or os.path.splitext(file.filename)[0]
    uid = _uid(request)
    project = _handle_store_error(
        project_store.create_project, uid, content, project_name
    )
    insert_log(
        user_logs_db,
        uid,
        "kemkim.project.create",
        "kemkim",
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
        raise HTTPException(400, "KEMKIM 분석 결과 zip 파일을 업로드해주세요.")
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
        "kemkim.project.create",
        "kemkim",
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
        "kemkim.project.rename",
        "kemkim",
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
        "kemkim.project.delete",
        "kemkim",
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
        "kemkim.project.move_folder",
        "kemkim",
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
        "kemkim.folder.create",
        "kemkim",
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
        "kemkim.folder.rename",
        "kemkim",
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
        "kemkim.folder.delete",
        "kemkim",
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
        "kemkim.project.download",
        "kemkim",
        target={"type": "project", "id": project_id, "name": project.get("name")},
    )
    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=f"{project['name']}.zip",
        background=BackgroundTask(os.remove, zip_path),
    )


# ---------------------------------------------------------------------------
# 분석 결과 조회 (좌표/신호/기간별 표/추적 — 전부 한 번에)
# ---------------------------------------------------------------------------


@router.get("/api/projects/{project_id}/graph")
async def project_graph(project_id: str, request: Request):
    graph = _handle_store_error(
        project_store.load_graph, _uid(request), project_id, _is_admin(request)
    )
    return JSONResponse(graph)


# ---------------------------------------------------------------------------
# 해석: 원본(토큰화 전) CSV 첨부 + 키워드 컨텍스트/AI 주제 추출
# ---------------------------------------------------------------------------


@router.post("/api/projects/{project_id}/source")
async def project_upload_source(
    project_id: str, request: Request, file: UploadFile = File(...)
):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "원본(토큰화 전) CSV 파일을 업로드해주세요.")
    content = await file.read()
    uid = _uid(request)
    _handle_store_error(project_store.save_source_csv, uid, project_id, content)
    insert_log(
        user_logs_db,
        uid,
        "kemkim.project.source_upload",
        "kemkim",
        target={"type": "project", "id": project_id},
        metadata={"filename": file.filename},
    )
    return JSONResponse({"message": "원본 CSV가 저장되었습니다."})


@router.post("/api/projects/{project_id}/interpret")
async def project_interpret(project_id: str, request: Request):
    uid = _uid(request)
    body = await request.json()

    keywords = [k for k in (body.get("keywords") or []) if k]
    if not keywords:
        raise HTTPException(400, "해석할 키워드를 선택해주세요.")
    match_mode = body.get("match_mode") or "or"
    if match_mode not in ("and", "or"):
        raise HTTPException(400, "match_mode는 and/or 중 하나여야 합니다.")
    use_ai = bool(body.get("use_ai"))

    graph = _handle_store_error(project_store.load_graph, uid, project_id)
    source_df = _handle_store_error(project_store.load_source_csv, uid, project_id)

    try:
        result = kemkim_analysis.run_interpretation(
            source_df, graph.get("metadata", {}), keywords, match_mode
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    ai_analysis = None
    ai_error = None
    if use_ai:
        if not result["titles"]:
            ai_error = (
                "제목(Title) 열이 없거나 검색 결과가 없어 AI 해석을 건너뛰었습니다."
            )
        else:
            session_token = request.cookies.get("session")
            if not session_token:
                ai_error = "AI 해석에는 로그인 세션이 필요합니다."
            else:
                try:
                    prompt = kemkim_analysis.build_topic_prompt(
                        ", ".join(keywords), result["titles"]
                    )
                    ai_analysis = kemkim_analysis.request_ai_topics(
                        analyze_service.MANAGER_SERVER_API, session_token, prompt
                    )
                except Exception as e:
                    ai_error = f"AI 해석 요청에 실패했습니다: {e}"

    interpretation = {
        "id": uuid.uuid4().hex,
        "keywords": keywords,
        "match_mode": match_mode,
        "created_at": kemkim_analysis.now_iso(),
        "date_col": result["date_col"],
        "text_col": result["text_col"],
        "title_col": result["title_col"],
        "matched_documents": result["matched_documents"],
        "results": result["results"],
        "ai_analysis": ai_analysis,
        "ai_error": ai_error,
    }
    saved = _handle_store_error(
        project_store.save_interpretation, uid, project_id, interpretation
    )
    insert_log(
        user_logs_db,
        uid,
        "kemkim.interpretation.run",
        "kemkim",
        target={"type": "project", "id": project_id},
        metadata={"keywords": keywords, "match_mode": match_mode, "use_ai": use_ai},
    )
    return JSONResponse(saved)


@router.get("/api/projects/{project_id}/interpretations")
async def project_interpretations(project_id: str, request: Request):
    interpretations = _handle_store_error(
        project_store.list_interpretations,
        _uid(request),
        project_id,
        _is_admin(request),
    )
    return JSONResponse({"interpretations": interpretations})


@router.get("/api/projects/{project_id}/interpretations/{interpretation_id}")
async def project_interpretation_detail(
    project_id: str, interpretation_id: str, request: Request
):
    interpretation = _handle_store_error(
        project_store.load_interpretation,
        _uid(request),
        project_id,
        interpretation_id,
        _is_admin(request),
    )
    return JSONResponse(interpretation)


@router.get("/api/projects/{project_id}/interpretations/{interpretation_id}/export")
async def project_interpretation_export(
    project_id: str, interpretation_id: str, request: Request
):
    uid = _uid(request)
    interpretation = _handle_store_error(
        project_store.load_interpretation,
        uid,
        project_id,
        interpretation_id,
        _is_admin(request),
    )
    insert_log(
        user_logs_db,
        uid,
        "kemkim.interpretation.export",
        "kemkim",
        target={"type": "project", "id": project_id},
        metadata={"interpretation_id": interpretation_id},
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["keyword", "title", "date", "context", "full_text"])
    for entry in interpretation.get("results", []):
        keyword = entry["keyword"]
        for m in entry.get("matches", []):
            writer.writerow(
                [
                    keyword,
                    m.get("title") or "",
                    m.get("date") or "",
                    m.get("context") or "",
                    m.get("full_text") or "",
                ]
            )

    csv_bytes = ("﻿" + buf.getvalue()).encode("utf-8")
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="keyword_context_{interpretation_id}.csv"'
        },
    )


# ---------------------------------------------------------------------------
# 실행(분석): 토큰 CSV 업로드 -> manager/server /analysis/kemkim 호출
# ---------------------------------------------------------------------------


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
    data["files"] = [f for f in data.get("files", []) if f.get("type") == "token"]
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
    suggested_start, suggested_end = _suggest_date_range(filename)
    insert_log(
        user_logs_db,
        _uid(request),
        "kemkim.project.import_from_crawl_db",
        "kemkim",
        target={"type": "crawl_db", "id": uid, "name": name},
    )
    return JSONResponse(
        {
            "stage_id": stage_id,
            "suggested_name": os.path.splitext(filename)[0],
            "suggested_start_date": suggested_start,
            "suggested_end_date": suggested_end,
        }
    )


@router.post("/api/projects/analyze/upload")
async def api_analyze_upload_stage(request: Request, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "토큰화된 CSV 파일을 업로드해주세요.")
    content = await file.read()
    stage_id = upload_staging.stage(_uid(request), content, file.filename)
    suggested_start, suggested_end = _suggest_date_range(file.filename)
    return JSONResponse(
        {
            "stage_id": stage_id,
            "suggested_name": os.path.splitext(file.filename)[0],
            "suggested_start_date": suggested_start,
            "suggested_end_date": suggested_end,
        }
    )


@router.post("/api/projects/analyze/start")
async def api_analyze_start(request: Request):
    uid = _uid(request)

    body = await request.json()
    try:
        content, filename = upload_staging.pop(uid, body.get("stage_id", ""))
    except ValueError as e:
        raise HTTPException(400, str(e))

    raw_option = body.get("option") or {}
    if not raw_option.get("startdate") or not raw_option.get("enddate"):
        raise HTTPException(400, "분석 시작일/종료일을 선택해주세요 (YYYYMMDD).")

    built_option = analyze_service.build_option(raw_option)

    project_name = (body.get("name") or "").strip() or os.path.splitext(filename)[0]
    pid = analyze_service.start_job(
        content, filename, built_option, uid, project_name=project_name
    )
    insert_log(
        user_logs_db,
        uid,
        "kemkim.project.analyze_start",
        "kemkim",
        target={"type": "project", "id": pid, "name": project_name},
        metadata={
            "startdate": raw_option.get("startdate"),
            "enddate": raw_option.get("enddate"),
        },
    )
    return JSONResponse({"pid": pid})


@router.get("/api/projects/analyze/{pid}/status")
async def api_analyze_status(pid: str, request: Request):
    _uid(request)
    return JSONResponse(analyze_service.get_job(pid))
