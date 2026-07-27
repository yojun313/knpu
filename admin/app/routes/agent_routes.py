from fastapi import APIRouter, Request, Depends, HTTPException, Body
from fastapi.templating import Jinja2Templates
from app.routes.dependencies import get_current_user
from app.services import agent_service

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/agents")
async def agents_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse(
        request=request,
        name="agents.html",
        context={
            "active_page": "agents",
            "projects": agent_service.PROJECT_ROOTS,
        },
    )


@router.get("/api/agents/sessions")
async def api_list_sessions(cwd: str, user=Depends(get_current_user)):
    if not agent_service.is_allowed_cwd(cwd):
        raise HTTPException(status_code=400, detail="허용되지 않은 디렉토리입니다")

    live = {s["sessionId"]: s for s in agent_service.list_live_sessions(cwd)}
    transcripts = agent_service.list_transcript_sessions(cwd)

    sessions = []
    for t in transcripts:
        live_info = live.get(t["session_id"])
        sessions.append(
            {
                **t,
                "status": live_info.get("status", "running")
                if live_info
                else "completed",
                "kind": live_info.get("kind") if live_info else "background",
            }
        )
    return {"sessions": sessions}


@router.get("/api/agents/sessions/{session_id}/transcript")
async def api_transcript(session_id: str, cwd: str, user=Depends(get_current_user)):
    if not agent_service.is_allowed_cwd(cwd):
        raise HTTPException(status_code=400, detail="허용되지 않은 디렉토리입니다")
    return {"messages": agent_service.read_transcript(cwd, session_id)}


@router.post("/api/agents/sessions")
async def api_create_session(
    cwd: str = Body(...),
    prompt: str = Body(...),
    name: str | None = Body(None),
    user=Depends(get_current_user),
):
    if not agent_service.is_allowed_cwd(cwd):
        raise HTTPException(status_code=400, detail="허용되지 않은 디렉토리입니다")
    try:
        result = agent_service.create_session(cwd, prompt, name)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return result


@router.post("/api/agents/sessions/{session_id}/messages")
async def api_send_message(
    session_id: str,
    cwd: str = Body(...),
    prompt: str = Body(...),
    user=Depends(get_current_user),
):
    if not agent_service.is_allowed_cwd(cwd):
        raise HTTPException(status_code=400, detail="허용되지 않은 디렉토리입니다")
    try:
        result = agent_service.send_message(cwd, session_id, prompt)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return result
