from fastapi import APIRouter, Request, Depends, Query
from fastapi.templating import Jinja2Templates
from app.services.data_service import get_dashboard_stats, get_recent_logs, get_recent_crawlers
from app.routes.dependencies import get_current_user
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
from fastapi.responses import RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exception_handlers import http_exception_handler

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/")
async def read_overview(
    request: Request, 
    date: Optional[str] = Query(None), 
    user=Depends(get_current_user)
):
    today_str = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")
    
    target_date = date if date else today_str
    
    stats = get_dashboard_stats(date_str=target_date)
    logs = get_recent_logs(limit=10, date_str=target_date)
    crawlers = get_recent_crawlers(5)
    
    return templates.TemplateResponse("overview.html", {
        "request": request, 
        "stats": stats, 
        "logs": logs, 
        "crawlers": crawlers, 
        "active_page": "overview",
        "today": today_str,
        "search_date": target_date
    })
    
@router.exception_handler(StarletteHTTPException)
async def auth_exception_handler(request: Request, exc: StarletteHTTPException):
    # 로그인 안 된 상태(307)에서 예외가 발생하면 /login으로 리다이렉트
    if exc.status_code == 307:
        return RedirectResponse(url="/login")
    
    # 그 외의 에러는 기본 에러 메시지 출력
    return await http_exception_handler(request, exc)