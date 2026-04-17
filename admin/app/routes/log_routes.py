from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from app.services.data_service import get_recent_logs, get_user_mapping
from app.routes.dependencies import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/logs")
async def read_logs(request: Request, name: Optional[str] = None, date: Optional[str] = None, user=Depends(get_current_user)):
    if date is None:
        date = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")
        
    logs = get_recent_logs(50, name=name, date_str=date)
    user_map = get_user_mapping()
    user_names = sorted(list(set([u_name for u_name in user_map.values() if u_name and u_name != "알 수 없음"])))
    
    return templates.TemplateResponse("logs.html", {
        "request": request, "logs": logs, "active_page": "logs", 
        "search_name": name, "search_date": date, "user_names": user_names 
    })