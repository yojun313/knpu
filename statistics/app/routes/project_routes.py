# app/routes/project_routes.py
import asyncio
import os
import time
import uuid

import requests
from fastapi import APIRouter, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse, Response
from starlette.background import BackgroundTask

from app.services import project_store, analyze_service, ai_analysis
from system import uploads as upload_staging
from system.jobs import submit as submit_job
from system.jobs.routes import parse_schedule, status_compat as job_status_compat
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


@router.get("/api/projects/{project_id}/graphs/{name}")
async def project_graph(project_id: str, name: str, request: Request):
    """결과물 graphs/ 폴더의 PNG(워드클라우드 등)를 서빙한다."""
    path = _handle_store_error(
        project_store.graph_path, _uid(request), project_id, name, _is_admin(request)
    )
    return FileResponse(path, media_type="image/png")


@router.get("/api/projects/{project_id}/base")
async def project_base(project_id: str, request: Request):
    base = _handle_store_error(
        project_store.load_base, _uid(request), project_id, _is_admin(request)
    )
    return JSONResponse(base)


# ---------------------------------------------------------------------------
# AI 분석 — LLM 응답이 nginx 기본 60초를 넘기 쉬워 백그라운드 작업 + 폴링으로 돈다.
# (uvicorn 워커가 하나라 메모리 레지스트리로 충분하다.)
# ---------------------------------------------------------------------------

# 실행 중인 작업(이 프로세스에서 돌고 있는 것)만 메모리에 둔다. 진행 상황 자체는
# project_store 가 프로젝트 폴더의 ai_jobs.json 에 남겨서, 페이지를 벗어나거나 다른
# 기기에서 접속해도 같은 계정이면 그대로 보인다. 서버가 재시작되면 메모리에 없는
# "진행 중" 작업은 중단된 것으로 표시한다.
_ai_live: dict[str, dict] = {}
_AI_KEEP_DONE_SEC = 120  # 끝난 작업은 잠깐 목록에 남겨 다른 창도 완료를 알아채게 한다


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _job_public(job: dict) -> dict:
    keys = (
        "id",
        "mode",
        "label",
        "question",
        "table_id",
        "status",
        "stage",
        "error",
        "result_id",
        "created_at",
        "updated_at",
        "kind",
    )
    out = {k: job.get(k) for k in keys}
    live = _ai_live.get(job.get("id"))
    if live and live.get("prompt"):
        out["has_prompt"] = True
    return out


def _settle_jobs(owner: str, project_id: str) -> list:
    """메모리에 없는데 진행 중으로 남은 작업(서버 재시작 등)을 중단으로 정리한다."""

    def fix(items):
        changed = False
        for j in items:
            if j.get("status") == "running" and j.get("id") not in _ai_live:
                j["status"] = "error"
                j["error"] = (
                    "서버가 다시 시작되어 작업이 중단되었습니다. 다시 실행해 주세요."
                )
                j["updated_at"] = _now_iso()
                changed = True
        return items if changed else items

    items = project_store.read_ai_jobs(owner, project_id)
    if any(j.get("status") == "running" and j.get("id") not in _ai_live for j in items):
        items = project_store.update_ai_jobs(owner, project_id, fix)
        # 대화에 남은 "답변 중" 자리표시도 같이 정리
        for j in items:
            if j.get("kind") == "chat" and j.get("status") == "error":
                _finish_chat_message(
                    owner, project_id, j["uid"], j["id"], error=j["error"]
                )
    return items


def _finish_chat_message(owner, project_id, uid, job_id, message=None, error=None):
    def fix(items):
        for i, m in enumerate(items):
            if m.get("job_id") == job_id and m.get("pending"):
                items[i] = message or {
                    "role": "assistant",
                    "error": True,
                    "content": error or "AI 분석에 실패했습니다.",
                    "job_id": job_id,
                    "created_at": _now_iso(),
                }
        return items

    project_store.update_ai_chat(owner, project_id, uid, fix)


@router.post("/api/projects/{project_id}/ai-analysis")
async def project_ai_analysis(project_id: str, request: Request):
    user = _user(request)
    uid = user["uid"]
    is_admin = _is_admin(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(400, "AI 분석 요청 형식이 올바르지 않습니다.")
    mode = str(body.get("mode") or "")
    if mode not in ai_analysis.MODES:
        raise HTTPException(400, "지원하지 않는 AI 분석 방식입니다.")
    question = str(body.get("question") or "").strip()[:2000]
    if mode in ("question", "chat") and not question:
        raise HTTPException(400, "AI에게 물어볼 질문을 입력해주세요.")
    owner = _handle_store_error(project_store.project_owner, uid, project_id, is_admin)
    base = _handle_store_error(project_store.load_base, uid, project_id, is_admin)
    table_id = body.get("table_id") if mode == "table" else None
    if mode == "table":
        try:
            ai_analysis.select_tables(base, "table", table_id)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e

    running = [j for j in _ai_live.values() if j["uid"] == uid]
    if len(running) >= 3:
        raise HTTPException(
            429, "진행 중인 AI 분석이 3개 있습니다. 끝난 뒤 다시 요청해 주세요."
        )
    if mode == "chat" and any(
        j["project_id"] == project_id and j["kind"] == "chat" for j in running
    ):
        raise HTTPException(
            409, "이전 질문에 대한 답변을 준비하고 있습니다. 끝난 뒤 다시 보내 주세요."
        )

    job_id = uuid.uuid4().hex
    label = (
        ai_analysis.REPORT_MODES.get(mode, {}).get("label")
        if mode not in ("chat", "question", "table")
        else None
    )
    if mode == "question":
        label = question[:120]
    if mode == "table":
        label = next(
            (
                t.get("title")
                for t in base.get("tables") or []
                if t.get("id") == table_id
            ),
            table_id,
        )
    if mode == "chat":
        label = question[:120]
    now = _now_iso()
    job = {
        "id": job_id,
        "uid": uid,
        "project_id": project_id,
        "kind": "chat" if mode == "chat" else "report",
        "mode": mode,
        "label": label,
        "question": question or None,
        "table_id": table_id,
        "status": "running",
        "stage": "대기 중",
        "error": None,
        "result_id": None,
        "created_at": now,
        "updated_at": now,
    }
    live = {**job, "prompt": None}
    _ai_live[job_id] = live  # 저장보다 먼저 — 그 사이 조회가 '중단됨'으로 오판하지 않게
    project_store.save_ai_job(owner, project_id, job)

    history = None
    if mode == "chat":
        # 대화 기록은 서버에 있는 것을 쓴다(다른 기기에서 이어 물어도 맥락이 같다).
        prior = project_store.read_ai_chat(owner, project_id, uid)
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in prior
            if not m.get("pending") and not m.get("error") and m.get("content")
        ][-10:]
        project_store.update_ai_chat(
            owner,
            project_id,
            uid,
            lambda items: (
                items
                + [
                    {"role": "user", "content": question, "created_at": now},
                    {
                        "role": "assistant",
                        "pending": True,
                        "job_id": job_id,
                        "created_at": now,
                    },
                ]
            ),
        )

    def persist(**changes):
        job.update(changes, updated_at=_now_iso())
        live.update(changes)
        project_store.save_ai_job(owner, project_id, job)

    def progress(stage, prompt=None):
        if prompt is not None:
            live["prompt"] = prompt
        if stage != job.get("stage"):
            persist(stage=stage)

    async def worker():
        from system.llm import LLMError

        err = None
        try:
            if mode == "chat":
                res = await ai_analysis.run_chat(base, uid, question, history, progress)
                msg = {
                    "role": "assistant",
                    "content": res["text"],
                    "tables": res["tables"],
                    "steps": res["steps"],
                    "llm": res["llm"],
                    "job_id": job_id,
                    "created_at": _now_iso(),
                }
                await asyncio.to_thread(
                    _finish_chat_message, owner, project_id, uid, job_id, msg
                )
                await asyncio.to_thread(persist, status="done", stage="완료")
            else:
                res = await ai_analysis.run_report(
                    base, uid, mode, table_id, question, progress
                )
                saved = await asyncio.to_thread(
                    project_store.add_ai_result, uid, project_id, res, is_admin
                )
                await asyncio.to_thread(
                    persist, status="done", stage="완료", result_id=saved["id"]
                )
        except (ValueError, LLMError) as e:
            err = str(e)
        except Exception as e:  # 예상 못 한 오류도 화면에 알린다
            err = f"AI 분석 중 오류가 발생했습니다: {e}"
        try:
            if err:
                await asyncio.to_thread(
                    persist, status="error", stage="실패", error=err
                )
                if mode == "chat":
                    await asyncio.to_thread(
                        _finish_chat_message, owner, project_id, uid, job_id, None, err
                    )
        finally:
            # 최종 상태를 디스크에 쓴 뒤에 메모리에서 뺀다.
            _ai_live.pop(job_id, None)

    asyncio.create_task(worker())
    return JSONResponse({"job_id": job_id, "job": _job_public(job)}, status_code=202)


@router.get("/api/projects/{project_id}/ai-state")
async def ai_state(project_id: str, request: Request):
    """이 계정의 진행 중/실패 작업, 대화, 저장된 결과 목록 버전을 한 번에 돌려준다."""
    uid = _uid(request)
    owner = _handle_store_error(
        project_store.project_owner, uid, project_id, _is_admin(request)
    )
    jobs = await asyncio.to_thread(_settle_jobs, owner, project_id)
    import time as _t
    from datetime import datetime

    def recent(j):
        if j.get("status") != "done":
            return True
        try:
            ts = datetime.fromisoformat(j["updated_at"]).timestamp()
        except (KeyError, ValueError):
            return False
        return _t.time() - ts < _AI_KEEP_DONE_SEC

    mine = [
        _job_public(j)
        for j in jobs
        if j.get("uid") == uid and not j.get("dismissed") and recent(j)
    ]
    chat = await asyncio.to_thread(project_store.read_ai_chat, owner, project_id, uid)
    results = await asyncio.to_thread(
        project_store.read_ai_results_meta, owner, project_id
    )
    return JSONResponse({"jobs": mine, "chat": chat, "results_version": results})


@router.get("/api/ai-activity")
async def ai_activity(request: Request):
    """다른 프로젝트를 보고 있어도 사이드바에 '분석 중' 표시를 하기 위한 요약."""
    uid = _uid(request)
    items = [
        {
            "project_id": j["project_id"],
            "kind": j["kind"],
            "label": j.get("label"),
            "stage": j.get("stage"),
        }
        for j in _ai_live.values()
        if j["uid"] == uid
    ]
    return JSONResponse({"running": items})


@router.get("/api/ai-jobs/{job_id}/prompt")
async def ai_job_prompt(job_id: str, request: Request):
    live = _ai_live.get(job_id)
    if not live or live["uid"] != _uid(request) or not live.get("prompt"):
        raise HTTPException(404, "프롬프트를 찾을 수 없습니다.")
    return JSONResponse({"prompt": live["prompt"]})


@router.delete("/api/projects/{project_id}/ai-jobs/{job_id}")
async def ai_job_dismiss(project_id: str, job_id: str, request: Request):
    uid = _uid(request)
    owner = _handle_store_error(
        project_store.project_owner, uid, project_id, _is_admin(request)
    )

    def fix(items):
        for j in items:
            if (
                j.get("id") == job_id
                and j.get("uid") == uid
                and j.get("status") != "running"
            ):
                j["dismissed"] = True
        return items

    await asyncio.to_thread(project_store.update_ai_jobs, owner, project_id, fix)
    return JSONResponse({"ok": True})


@router.delete("/api/projects/{project_id}/ai-chat")
async def ai_chat_clear(project_id: str, request: Request):
    uid = _uid(request)
    owner = _handle_store_error(
        project_store.project_owner, uid, project_id, _is_admin(request)
    )
    if any(
        j["uid"] == uid and j["project_id"] == project_id and j["kind"] == "chat"
        for j in _ai_live.values()
    ):
        raise HTTPException(409, "답변을 준비하는 중에는 대화를 지울 수 없습니다.")
    await asyncio.to_thread(
        project_store.update_ai_chat, owner, project_id, uid, lambda items: []
    )
    return JSONResponse({"ok": True})


@router.get("/api/projects/{project_id}/ai-results")
async def ai_results(project_id: str, request: Request):
    items = _handle_store_error(
        project_store.list_ai_results, _uid(request), project_id, _is_admin(request)
    )
    # 프롬프트는 크기가 커서 목록에서는 빼고, 펼칠 때 따로 받는다.
    return JSONResponse(
        {
            "results": [
                {k: v for k, v in i.items() if k != "prompt"}
                | {"has_prompt": bool(i.get("prompt"))}
                for i in items
            ]
        }
    )


@router.get("/api/projects/{project_id}/ai-results/{result_id}/prompt")
async def ai_result_prompt(project_id: str, result_id: str, request: Request):
    items = _handle_store_error(
        project_store.list_ai_results, _uid(request), project_id, _is_admin(request)
    )
    item = next((i for i in items if i.get("id") == result_id), None)
    if item is None:
        raise HTTPException(404, "AI 분석 결과를 찾을 수 없습니다.")
    return JSONResponse({"prompt": item.get("prompt") or ""})


@router.delete("/api/projects/{project_id}/ai-results/{result_id}")
async def ai_result_delete(project_id: str, result_id: str, request: Request):
    _handle_store_error(
        project_store.delete_ai_result,
        _uid(request),
        project_id,
        result_id,
        _is_admin(request),
    )
    return JSONResponse({"ok": True})


@router.get("/api/projects/{project_id}/ai-results/{result_id}.md")
async def ai_result_markdown(project_id: str, result_id: str, request: Request):
    items = _handle_store_error(
        project_store.list_ai_results, _uid(request), project_id, _is_admin(request)
    )
    item = next((i for i in items if i.get("id") == result_id), None)
    if item is None:
        raise HTTPException(404, "AI 분석 결과를 찾을 수 없습니다.")
    from urllib.parse import quote

    name = quote(f"AI분석_{item.get('label') or 'result'}.md")
    return Response(
        ai_analysis.to_markdown(item),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{name}"},
    )


# ---------------------------------------------------------------------------
# 실행(분석): 원본 CSV 업로드 -> manager/server /analysis/statistics 호출
# ---------------------------------------------------------------------------


@router.get("/api/analyze/options")
async def analyze_options():
    return JSONResponse(
        {
            "platforms": analyze_service.PLATFORM_CATEGORIES,
            "common_category": analyze_service.COMMON_CATEGORY,  # 하위 호환
            "common_categories": analyze_service.COMMON_CATEGORIES,
            "wordcloud_category": analyze_service.WORDCLOUD_CATEGORY,
        }
    )


@router.get("/api/gpu/stats")
async def api_gpu_stats(request: Request):
    """GPU 서버의 nvidia-smi 실시간 사용량 (사이드바 하단 모니터 위젯용)."""
    _uid(request)
    if not analyze_service.GPU_SERVER_URL:
        return JSONResponse({"gpus": [], "error": "GPU_SERVER_URL 미설정"})
    try:
        resp = requests.get(
            f"{analyze_service.GPU_SERVER_URL}/analysis/gpu/stats", timeout=8
        )
        return JSONResponse(resp.json())
    except Exception as e:
        return JSONResponse({"gpus": [], "error": str(e)})


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
    # raw(원본)는 일반 통계, token(토큰화)은 워드클라우드 분석용 — 둘 다 보여주고
    # 프론트가 종류 배지로 구분한다.
    data["files"] = [
        f for f in data.get("files", []) if f.get("type") in ("raw", "token")
    ]
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
    extra_options = (
        body.get("options") if isinstance(body.get("options"), dict) else None
    )
    try:
        params = analyze_service.build_job_params(category, platform, extra_options)
    except ValueError as e:
        raise HTTPException(400, str(e))
    scheduled = parse_schedule(body.get("scheduled_at"))
    job = await asyncio.to_thread(
        submit_job,
        service="statistics",
        kind="statistics",
        kind_label=analyze_service.job_kind_label(category),
        user=_user(request),
        title=project_name,
        params=params,
        content=content,
        filename=filename,
        scheduled_ts=scheduled,
    )
    insert_log(
        user_logs_db,
        uid,
        "statistics.project.analyze_start",
        "statistics",
        target={"type": "job", "id": job["_id"], "name": project_name},
        metadata={
            "category": category,
            "platform": platform,
            "scheduled_ts": job.get("scheduled_ts"),
        },
    )
    return JSONResponse(
        {"pid": job["_id"], "job_id": job["_id"], "status": job["status"]}
    )


@router.get("/api/projects/analyze/{pid}/status")
async def api_analyze_status(pid: str, request: Request):
    return JSONResponse(job_status_compat(_uid(request), pid))
