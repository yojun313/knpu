import os
from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from app.services.data_service import (
    get_recent_bugs,
    get_user_bugs,
    get_user_bug_by_uid,
    get_user_mapping,
)
from app.services import agent_service
from app.routes.dependencies import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

_KNPU_ROOT = "/home/lab/knpu"


def _detect_service_dir(message: str) -> str | None:
    idx = message.find("knpu/")
    if idx == -1:
        return None
    rest = message[idx + len("knpu/") :]
    service = rest.split("/")[0].strip()
    candidate = os.path.join(_KNPU_ROOT, service)
    if service and os.path.isdir(candidate):
        return candidate
    return None


@router.post("/api/bugs/{uid}/auto-fix")
async def auto_fix_bug(uid: str, user=Depends(get_current_user)):
    bug = get_user_bug_by_uid(uid)
    if not bug:
        raise HTTPException(status_code=404, detail="버그를 찾을 수 없습니다")

    message = bug.get("message", "")
    service_dir = _detect_service_dir(message)
    if not service_dir:
        raise HTTPException(
            status_code=422,
            detail="에러 메시지에서 어느 서비스인지 식별할 수 없습니다 (knpu/<service>/ 경로 없음)",
        )

    prompt = (
        "다음 버그 리포트를 분석하고 근본 원인을 고쳐줘.\n\n"
        f"{message}\n\n"
        "제약:\n"
        "- 이 디렉토리(현재 작업 디렉토리) 안의 코드만 수정해.\n"
        "- 수정 후 git commit까지만 하고, git push나 서비스 재시작(pm2 restart 등)은 하지 마 — "
        "배포는 사람이 직접 확인하고 진행해.\n"
        "- 수정이 끝나면 무엇을 왜 고쳤는지 한국어로 간단히 요약해줘."
    )

    try:
        result = agent_service.create_session(
            service_dir, prompt, name=f"bugfix-{uid[:8]}"
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"session_id": result["session_id"], "cwd": service_dir}


@router.get("/bugs")
async def read_user_bugs(
    request: Request,
    name: Optional[str] = None,
    date: Optional[str] = None,
    user=Depends(get_current_user),
):
    bugs = get_user_bugs(50, name=name, date_str=date)
    user_map = get_user_mapping()
    user_names = sorted(
        list(
            set(
                [
                    u_name
                    for u_name in user_map.values()
                    if u_name and u_name != "알 수 없음"
                ]
            )
        )
    )

    return templates.TemplateResponse(
        request=request,
        name="bugs.html",
        context={
            "bugs": bugs,
            "active_page": "user_bugs",
            "search_name": name,
            "search_date": date,
            "user_names": user_names,
        },
    )


@router.get("/bug-reports")
async def read_bugs(request: Request, user=Depends(get_current_user)):
    bugs = get_recent_bugs(50)
    return templates.TemplateResponse(
        request=request,
        name="bug-reports.html",
        context={"bugs": bugs, "active_page": "bugs"},
    )
