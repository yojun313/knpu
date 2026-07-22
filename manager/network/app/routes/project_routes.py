# app/routes/project_routes.py
import os

from fastapi import APIRouter, UploadFile, File, Form, Query, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse

from app.services import project_store, graph_analysis

router = APIRouter()

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
MAX_EDGES_DEFAULT = 4000


def _uid(request: Request) -> str:
    user = request.scope.get("state", {}).get("user")
    if not user:
        # 미들웨어가 이미 /api/* 는 401로 막아주므로 정상 흐름에서는 도달하지 않는다.
        raise HTTPException(401, "인증이 필요합니다")
    return user["uid"]


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
    """프로젝트 목록(왼쪽 레일)과 그래프 뷰어가 한 화면에 있는 통합 UI. 프로젝트를
    아직 선택하지 않은 상태로 열린다."""
    return FileResponse(os.path.join(STATIC_DIR, "viewer.html"))


@router.get("/viewer", response_class=HTMLResponse)
async def app_shell_viewer():
    return FileResponse(os.path.join(STATIC_DIR, "viewer.html"))


@router.get("/api/me")
async def api_me(request: Request):
    user = request.scope.get("state", {}).get("user")
    if not user:
        raise HTTPException(401, "인증이 필요합니다")
    return JSONResponse(user)


@router.get("/api/projects")
async def api_list_projects(request: Request):
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
    project = _handle_store_error(
        project_store.create_project, _uid(request), content, project_name
    )
    return JSONResponse(project)


@router.patch("/api/projects/{project_id}")
async def api_rename_project(project_id: str, request: Request):
    body = await request.json()
    project = _handle_store_error(
        project_store.rename_project, _uid(request), project_id, body.get("name", "")
    )
    return JSONResponse(project)


@router.delete("/api/projects/{project_id}")
async def api_delete_project(project_id: str, request: Request):
    _handle_store_error(project_store.delete_project, _uid(request), project_id)
    return JSONResponse({"message": "삭제되었습니다"})


@router.get("/viewer/{project_id}", response_class=HTMLResponse)
async def viewer_page(project_id: str, request: Request):
    _handle_store_error(project_store.get_project, _uid(request), project_id)
    return FileResponse(os.path.join(STATIC_DIR, "viewer.html"))


@router.get("/api/projects/{project_id}/meta")
async def project_meta(project_id: str, request: Request):
    return JSONResponse(
        _handle_store_error(project_store.get_project, _uid(request), project_id)
    )


@router.get("/api/projects/{project_id}/summary")
async def project_summary(project_id: str, request: Request, tag: str = Query("")):
    graph = _handle_store_error(
        project_store.load_graph, _uid(request), project_id, tag
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
        project_store.load_graph, _uid(request), project_id, tag
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


@router.post("/api/internal/projects/ingest")
async def internal_ingest(
    uid: str = Form(...), name: str = Form(...), file: UploadFile = File(...)
):
    """매니저 서버가 분석 완료 직후 결과 zip을 사용자 프로젝트로 곧바로 밀어 넣을 때 쓰는
    내부 전용 엔드포인트. 미들웨어의 X-Internal-Key 통과 경로로만 접근 가능하다."""
    content = await file.read()
    project = _handle_store_error(
        project_store.create_project, uid, content, name, "manager"
    )
    return JSONResponse(project)
