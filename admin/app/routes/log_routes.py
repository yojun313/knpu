from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from app.services.data_service import (
    get_recent_logs,
    get_user_mapping,
    get_audit_logs,
    get_audit_services,
)
from app.routes.dependencies import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/logs")
async def read_logs(
    request: Request,
    name: Optional[str] = None,
    date: Optional[str] = None,
    user=Depends(get_current_user),
):
    if date is None:
        date = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")

    logs = get_recent_logs(50, name=name, date_str=date)
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
        name="logs.html",
        context={
            "logs": logs,
            "active_page": "logs",
            "search_name": name,
            "search_date": date,
            "user_names": user_names,
        },
    )


@router.get("/audit-logs")
async def read_audit_logs(
    request: Request,
    service: Optional[str] = None,
    method: Optional[str] = None,
    name: Optional[str] = None,
    date: Optional[str] = None,
    page: int = 1,
    user=Depends(get_current_user),
):
    per_page = 30
    page = max(1, page)
    logs, total = get_audit_logs(
        page=page,
        per_page=per_page,
        service=service,
        name=name,
        method=method,
        date_str=date,
    )
    total_pages = max(1, (total + per_page - 1) // per_page)

    return templates.TemplateResponse(
        request=request,
        name="audit-logs.html",
        context={
            "logs": logs,
            "active_page": "audit_logs",
            "services": get_audit_services(),
            "search_service": service,
            "search_method": method,
            "search_name": name,
            "search_date": date,
            "page": page,
            "total_pages": total_pages,
            "total": total,
        },
    )
