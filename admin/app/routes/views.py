from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from app.services.data_service import get_dashboard_stats, get_recent_logs, get_recent_crawlers, get_recent_bugs, get_user_bugs, get_user_mapping

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/")
async def read_overview(request: Request):
    # 기존 코드 유지
    stats = get_dashboard_stats()
    logs = get_recent_logs(10)
    crawlers = get_recent_crawlers(5)
    return templates.TemplateResponse("overview.html", {"request": request, "stats": stats, "logs": logs, "crawlers": crawlers, "active_page": "overview"})

@router.get("/logs")
async def read_logs(request: Request, name: Optional[str] = None, date: Optional[str] = None):
    if date is None:
        date = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")
        
    logs = get_recent_logs(50, name=name, date_str=date)
    
    user_map = get_user_mapping()
    user_names = sorted(list(set([u_name for u_name in user_map.values() if u_name and u_name != "알 수 없음"])))
    
    return templates.TemplateResponse("logs.html", {
        "request": request, 
        "logs": logs, 
        "active_page": "logs", 
        "search_name": name, 
        "search_date": date,
        "user_names": user_names 
    })

@router.get("/bugs")
async def read_user_bugs(request: Request, name: Optional[str] = None, date: Optional[str] = None):
    if date is None:
        date = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")
        
    bugs = get_user_bugs(50, name=name, date_str=date)

    user_map = get_user_mapping()
    user_names = sorted(list(set([u_name for u_name in user_map.values() if u_name and u_name != "알 수 없음"])))
    
    return templates.TemplateResponse("bugs.html", {
        "request": request, 
        "bugs": bugs, 
        "active_page": "user_bugs", 
        "search_name": name, 
        "search_date": date,
        "user_names": user_names
    })
    
@router.get("/crawlers")
async def read_crawlers(request: Request):
    stats = get_dashboard_stats()
    crawlers = get_recent_crawlers(50)
    return templates.TemplateResponse("crawlers.html", {"request": request, "crawlers": crawlers, "stats": stats, "active_page": "crawlers"})

@router.get("/bug-reports")
async def read_bugs(request: Request):
    bugs = get_recent_bugs(50)
    return templates.TemplateResponse("bug-reports.html", {"request": request, "bugs": bugs, "active_page": "bugs"})