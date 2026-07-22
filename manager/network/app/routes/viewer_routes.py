# app/routes/viewer_routes.py
import os

from fastapi import APIRouter, UploadFile, File, Query, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse

from app.services import graph_store, graph_analysis

router = APIRouter()

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
MAX_EDGES_DEFAULT = 4000


@router.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@router.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "네트워크 분석 결과 zip 파일을 업로드해주세요.")
    content = await file.read()
    try:
        meta = graph_store.create_session(content, file.filename)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return JSONResponse(meta)


@router.get("/viewer/{session_id}", response_class=HTMLResponse)
async def viewer_page(session_id: str):
    try:
        graph_store.load_meta(session_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    return FileResponse(os.path.join(STATIC_DIR, "viewer.html"))


@router.get("/api/graph/{session_id}/meta")
async def graph_meta(session_id: str):
    try:
        return JSONResponse(graph_store.load_meta(session_id))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.get("/api/graph/{session_id}/summary")
async def graph_summary(session_id: str, tag: str = Query("")):
    try:
        graph = graph_store.load_graph(session_id, tag)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    summary = graph_analysis.compute_summary(graph)
    summary["community_keywords"] = graph_analysis.compute_community_keywords(graph)
    summary["tag"] = graph["tag"]
    summary["label"] = graph["label"]
    return JSONResponse(summary)


@router.get("/api/graph/{session_id}/data")
async def graph_data(
    session_id: str,
    tag: str = Query(""),
    full: bool = Query(False),
    max_edges: int = Query(MAX_EDGES_DEFAULT),
):
    try:
        graph = graph_store.load_graph(session_id, tag)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))

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
