from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from app.services.data_service import get_dashboard_stats, get_recent_crawlers
from app.routes.dependencies import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/crawlers")
async def read_crawlers(request: Request, user=Depends(get_current_user)):
    stats = get_dashboard_stats()
    crawlers = get_recent_crawlers(50)
    return templates.TemplateResponse("crawlers.html", {
        "request": request, "crawlers": crawlers, "stats": stats, "active_page": "crawlers"
    })