"""Git 관리 — UnivDash 의 Git 관리(여러 저장소 · 스테이징 · 브랜치 · 병합 · 스태시 · AI 커밋 메시지)를 옮겨 왔다.

저장소는 기본적으로 knpu 저장소와 그 옆(같은 상위 폴더)의 저장소를 찾는다.
GIT_REPOSITORIES / GIT_REPOSITORY_ROOTS 환경 변수(':' 구분)로 바꿀 수 있다.
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.db import user_logs_col
from app.routes.dependencies import get_current_user
from app.services import settings_service
from app.services.git_preferences import GitPreferences, GitPreferencesStore
from app.services.repo_git_service import GitService
from system.logging.user_log import insert_log

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["get_nav_items"] = settings_service.get_nav_items_ordered

# 저장소를 바꾸는 작업만 감사 로그에 남긴다(조회는 남기지 않음).
_AUDITED = {
    "pull",
    "push",
    "commit",
    "checkout",
    "create_branch",
    "delete_branch",
    "merge",
    "discard",
    "stash",
    "stash_pop",
    "stash_drop",
    "undo_commit",
    "revert",
    "abort_operation",
}


class GitActionRequest(BaseModel):
    rebase: bool = False
    force: bool = False
    paths: list[str] | None = Field(default=None, max_length=2000)
    message: str | None = Field(default=None, max_length=10000)
    amend: bool = False
    stage_all: bool = False
    push_after: bool = False
    branch: str | None = Field(default=None, max_length=255)
    start_point: str | None = Field(default=None, max_length=255)
    switch: bool = True
    no_ff: bool = False
    squash: bool = False
    include_untracked: bool = False
    stash_ref: str | None = Field(default=None, max_length=32)
    commit: str | None = Field(default=None, max_length=40)


class AISettingsRequest(BaseModel):
    base_url: str = Field(default="", max_length=500)
    model: str = Field(default="", max_length=120)
    token: str | None = Field(default=None, max_length=1000)  # None: 그대로, "": 지우기
    language: str = Field(default="auto", pattern=r"^(auto|ko|en)$")


class AIModelsRequest(BaseModel):
    base_url: str = Field(default="", max_length=500)
    token: str | None = Field(default=None, max_length=1000)


class AICommitRequest(BaseModel):
    stage_all: bool = True


def _raise_for(error: Exception):
    if isinstance(error, KeyError):
        raise HTTPException(
            status_code=404, detail=str(error.args[0] if error.args else error)
        ) from error
    if isinstance(error, ValueError):
        raise HTTPException(status_code=409, detail=str(error)) from error
    raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/git")
async def git_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse(
        request=request, name="git.html", context={"active_page": "git"}
    )


# ── AI 커밋 메시지 ──────────────────────────────────────────────────────────────


@router.get("/api/git/ai/settings")
async def get_ai_settings(user=Depends(get_current_user)):
    from app.services import ai_commit_service

    return await asyncio.to_thread(ai_commit_service.public_settings)


@router.put("/api/git/ai/settings")
async def save_ai_settings(body: AISettingsRequest, user=Depends(get_current_user)):
    from app.services import ai_commit_service

    try:
        return await asyncio.to_thread(
            ai_commit_service.save_settings,
            body.base_url,
            body.model,
            body.token,
            body.language,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/api/git/ai/models")
async def get_ai_models(body: AIModelsRequest, user=Depends(get_current_user)):
    from app.services import ai_commit_service

    try:
        return await asyncio.to_thread(
            ai_commit_service.discover_model, body.base_url, body.token
        )
    except ai_commit_service.AICommitError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/api/git/ai/commit-message/{repository_id}")
async def ai_commit_message(
    repository_id: str, body: AICommitRequest, user=Depends(get_current_user)
):
    from app.services import ai_commit_service

    try:
        return await asyncio.to_thread(
            ai_commit_service.generate,
            repository_id,
            body.stage_all,
            user.get("uid") or user.get("sub"),
        )
    except ai_commit_service.AICommitError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (KeyError, ValueError, RuntimeError) as error:
        _raise_for(error)


# ── 저장소 ──────────────────────────────────────────────────────────────────────


@router.get("/api/git/repositories")
async def get_repositories(status: bool = True, user=Depends(get_current_user)):
    repositories = await asyncio.to_thread(GitService.list_repositories, status)
    preferences = await asyncio.to_thread(GitPreferencesStore.load)
    return {"repositories": repositories, "preferences": preferences.model_dump()}


@router.put("/api/git/preferences")
async def save_preferences(preferences: GitPreferences, user=Depends(get_current_user)):
    saved = await asyncio.to_thread(GitPreferencesStore.save, preferences)
    return {"preferences": saved.model_dump()}


@router.get("/api/git/repositories/{repository_id}")
async def get_repository(repository_id: str, user=Depends(get_current_user)):
    try:
        return await asyncio.to_thread(GitService.get_repository_detail, repository_id)
    except (KeyError, ValueError, RuntimeError) as error:
        _raise_for(error)


@router.get("/api/git/repositories/{repository_id}/diff")
async def get_diff(
    repository_id: str,
    path: str = Query(..., min_length=1, max_length=4096),
    staged: bool = False,
    user=Depends(get_current_user),
):
    try:
        return await asyncio.to_thread(GitService.get_diff, repository_id, path, staged)
    except (KeyError, ValueError, RuntimeError) as error:
        _raise_for(error)


@router.get("/api/git/repositories/{repository_id}/commits/{commit_hash}")
async def get_commit(
    repository_id: str, commit_hash: str, user=Depends(get_current_user)
):
    try:
        return await asyncio.to_thread(
            GitService.get_commit, repository_id, commit_hash
        )
    except (KeyError, ValueError, RuntimeError) as error:
        _raise_for(error)


@router.post("/api/git/repositories/{repository_id}/{action}")
async def run_git_action(
    repository_id: str,
    action: str,
    payload: GitActionRequest,
    user=Depends(get_current_user),
):
    if action == "ruff_format":
        try:
            return await asyncio.to_thread(GitService.ruff_format, repository_id)
        except (KeyError, ValueError, RuntimeError) as error:
            _raise_for(error)
    if action not in GitService.ACTIONS:
        raise HTTPException(status_code=400, detail="지원하지 않는 Git 작업입니다.")
    outcome = "failure"
    try:
        result = await asyncio.to_thread(
            GitService.run_action, repository_id, action, payload.model_dump()
        )
        outcome = "success"
        return result
    except (KeyError, ValueError, RuntimeError) as error:
        _raise_for(error)
    finally:
        if action in _AUDITED:
            insert_log(
                user_logs_col,
                user.get("uid") or user.get("sub"),
                f"admin.git.{action}",
                "admin",
                message=f"git {action}"
                + (f" ({payload.branch})" if payload.branch else "")
                + (
                    f": {payload.message.splitlines()[0][:120]}"
                    if payload.message
                    else ""
                ),
                target={"type": "git_repository", "id": repository_id},
                outcome=outcome,
            )
