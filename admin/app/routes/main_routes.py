from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from app.services.data_service import get_dashboard_stats, get_recent_logs, get_recent_crawlers
from app.routes.dependencies import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/")
async def read_overview(request: Request, user=Depends(get_current_user)):
    stats = get_dashboard_stats()
    logs = get_recent_logs(10)
    crawlers = get_recent_crawlers(5)
    return templates.TemplateResponse("overview.html", {
        "request": request, "stats": stats, "logs": logs, "crawlers": crawlers, "active_page": "overview"
    })