from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from app.routes.dependencies import get_current_user
from app.services import git_service, settings_service
from app.db import user_logs_col
from system.logging.user_log import insert_log

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["get_nav_items"] = settings_service.get_nav_items_ordered


@router.get("/git")
async def git_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse(
        request=request, name="git.html", context={"active_page": "git"}
    )


@router.get("/api/git/status")
async def api_git_status(user=Depends(get_current_user)):
    return git_service.get_status()


@router.post("/api/git/fetch")
async def api_git_fetch(user=Depends(get_current_user)):
    try:
        git_service.fetch_all()
    except git_service.GitError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return git_service.get_status()


@router.post("/api/git/commit")
async def api_git_commit(
    message: str = Body(..., embed=True), user=Depends(get_current_user)
):
    try:
        git_service.commit_all(message)
    except git_service.GitError as e:
        raise HTTPException(status_code=400, detail=str(e))
    insert_log(
        user_logs_col,
        user["sub"],
        "admin.git.commit",
        "admin",
        message=f"git commit: {message}",
    )
    return git_service.get_status()


@router.post("/api/git/push")
async def api_git_push(user=Depends(get_current_user)):
    try:
        git_service.push_current()
    except git_service.GitError as e:
        raise HTTPException(status_code=400, detail=str(e))
    insert_log(user_logs_col, user["sub"], "admin.git.push", "admin")
    return git_service.get_status()


@router.post("/api/git/pull")
async def api_git_pull(user=Depends(get_current_user)):
    try:
        git_service.pull_current()
    except git_service.GitError as e:
        raise HTTPException(status_code=400, detail=str(e))
    insert_log(user_logs_col, user["sub"], "admin.git.pull", "admin")
    return git_service.get_status()


@router.post("/api/git/merge/preview")
async def api_git_merge_preview(
    branch: str = Body(..., embed=True), user=Depends(get_current_user)
):
    try:
        return git_service.merge_preview(branch)
    except git_service.GitError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/git/merge")
async def api_git_merge(
    branch: str = Body(..., embed=True), user=Depends(get_current_user)
):
    try:
        result = git_service.merge_into_main(branch)
    except git_service.GitError as e:
        raise HTTPException(status_code=400, detail=str(e))
    insert_log(
        user_logs_col,
        user["sub"],
        "admin.git.merge",
        "admin",
        message=f"git merge: {branch} -> main",
        target={"type": "git_branch", "id": branch},
    )
    status = git_service.get_status()
    status["merge_result"] = result
    return status


@router.get("/api/git/diff")
async def api_git_diff(path: str, user=Depends(get_current_user)):
    try:
        diff = git_service.get_file_diff(path)
    except git_service.GitError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"diff": diff}
