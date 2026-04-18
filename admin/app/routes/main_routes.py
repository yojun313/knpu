from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from app.services.data_service import get_dashboard_stats, get_recent_logs, get_recent_crawlers
from app.routes.dependencies import get_current_user
from datetime import datetime
from zoneinfo import ZoneInfo

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/")
async def read_overview(request: Request, user=Depends(get_current_user)):
    today_str = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")
    
    stats = get_dashboard_stats(date_str=today_str)
    logs = get_recent_logs(limit=10, date_str=today_str)
    crawlers = get_recent_crawlers(5) # 크롤러는 최근 실행 순서 유지
    
    return templates.TemplateResponse("overview.html", {
        "request": request, 
        "stats": stats, 
        "logs": logs, 
        "crawlers": crawlers, 
        "active_page": "overview",
        "today": today_str
    })