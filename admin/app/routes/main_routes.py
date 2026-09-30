from fastapi import APIRouter, Request, Depends, Query
from fastapi.templating import Jinja2Templates
from app.services.data_service import (
    get_dashboard_stats,
    get_recent_logs,
    get_recent_crawlers,
    get_overview_counts,
)
from app.services.pm2_service import PM2Service
from app.services.nginx_service import NginxService
from app.routes.dependencies import get_current_user
from app.services import settings_service
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["get_nav_items"] = settings_service.get_nav_items_ordered


@router.get("/")
async def read_overview(
    request: Request, date: Optional[str] = Query(None), user=Depends(get_current_user)
):
    today_str = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")
    target_date = date if date else today_str

    stats = get_dashboard_stats(date_str=target_date)
    logs = get_recent_logs(limit=10, date_str=target_date)
    crawlers = get_recent_crawlers(5)

    pm2_processes = PM2Service.get_processes()
    domains = NginxService.get_domains()
    attention_processes = [
        p.get("name", "이름 없음")
        for p in pm2_processes
        if p.get("pm2_env", {}).get("status") != "online"
    ]
    operations = {
        **get_overview_counts(target_date),
        "process_total": len(pm2_processes),
        "process_online": len(pm2_processes) - len(attention_processes),
        "attention_processes": attention_processes,
        "domain_count": len(domains),
        "path_count": sum(len(d.get("paths", [])) for d in domains),
    }
    metrics = [
        {
            "label": "운영 프로세스",
            "value": f"{operations['process_online']} / {operations['process_total']}",
            "detail": "PM2 온라인",
            "tone": "text-emerald-400",
        },
        {
            "label": "점검 필요",
            "value": len(attention_processes),
            "detail": ", ".join(attention_processes[:3]) or "중지된 프로세스 없음",
            "tone": "text-amber-400" if attention_processes else "text-emerald-400",
        },
        {
            "label": "연결 도메인",
            "value": operations["domain_count"],
            "detail": f"프록시 경로 {operations['path_count']}개",
            "tone": "text-blue-400",
        },
        {
            "label": "가입 승인 대기",
            "value": operations["pending_users"],
            "detail": "처리가 필요한 계정",
            "tone": "text-amber-400"
            if operations["pending_users"]
            else "text-zinc-200",
        },
        {
            "label": "실행 중 크롤링",
            "value": operations["running_crawls"],
            "detail": f"전체 DB {operations['total_crawls']}개",
            "tone": "text-blue-400",
        },
        {
            "label": "오류 크롤링",
            "value": operations["error_crawls"],
            "detail": "현재 오류 상태 DB",
            "tone": "text-red-400" if operations["error_crawls"] else "text-zinc-200",
        },
        {
            "label": "오늘 활동 기록",
            "value": stats["today_logs"],
            "detail": f"전체 {stats['total_logs']:,}건",
            "tone": "text-zinc-200",
        },
        {
            "label": "오늘 실패 기록",
            "value": operations["failed_events_today"],
            "detail": "실패로 기록된 작업",
            "tone": "text-red-400"
            if operations["failed_events_today"]
            else "text-emerald-400",
        },
        {
            "label": "오늘 사용자 제보",
            "value": stats["today_user_bugs"],
            "detail": f"전체 {stats['total_user_bugs']:,}건",
            "tone": "text-amber-400" if stats["today_user_bugs"] else "text-zinc-200",
        },
        {
            "label": "크롤링 저장소",
            "value": f"{stats['total_size_gb']:.2f} GB",
            "detail": "수집 DB 합계",
            "tone": "text-violet-400",
        },
    ]

    context = {
        "request": request,
        "stats": stats,
        "logs": logs,
        "crawlers": crawlers,
        "processes": pm2_processes,
        "operations": operations,
        "metrics": metrics,
        "active_page": "overview",
        "today": today_str,
        "search_date": target_date,
    }

    return templates.TemplateResponse(
        request=request, name="overview.html", context=context
    )
