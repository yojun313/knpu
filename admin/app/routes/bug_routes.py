from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from app.services.data_service import (
    get_recent_bugs,
    get_user_bugs,
    get_user_mapping,
    get_users_with_bug_report_counts,
    get_bug_reports_for_user,
    get_users_with_user_bug_counts,
    get_user_bugs_for_user,
)
from app.routes.dependencies import get_current_user
from app.services import settings_service

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["get_nav_items"] = settings_service.get_nav_items_ordered


@router.get("/bugs")
async def read_user_bugs(
    request: Request,
    name: Optional[str] = None,
    date: Optional[str] = None,
    selected_user: Optional[str] = None,
    page: int = 1,
    user=Depends(get_current_user),
):
    per_page = 30
    page = max(1, page)
    user_tabs = get_users_with_user_bug_counts()

    if selected_user:
        bugs, total = get_user_bugs_for_user(
            selected_user, page=page, per_page=per_page
        )
        total_pages = max(1, (total + per_page - 1) // per_page)
    else:
        bugs = get_user_bugs(50, name=name, date_str=date)
        total = len(bugs)
        total_pages = 1

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
            "user_tabs": user_tabs,
            "selected_user": selected_user,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "search_name": name,
            "search_date": date,
            "user_names": user_names,
        },
    )


@router.get("/bug-reports")
async def read_bugs(
    request: Request,
    selected_user: Optional[str] = None,
    page: int = 1,
    user=Depends(get_current_user),
):
    per_page = 30
    page = max(1, page)
    user_tabs = get_users_with_bug_report_counts()

    if selected_user:
        bugs, total = get_bug_reports_for_user(
            selected_user, page=page, per_page=per_page
        )
        total_pages = max(1, (total + per_page - 1) // per_page)
    else:
        bugs = get_recent_bugs(50)
        total = len(bugs)
        total_pages = 1

    return templates.TemplateResponse(
        request=request,
        name="bug-reports.html",
        context={
            "bugs": bugs,
            "active_page": "bugs",
            "user_tabs": user_tabs,
            "selected_user": selected_user,
            "page": page,
            "total_pages": total_pages,
            "total": total,
        },
    )
