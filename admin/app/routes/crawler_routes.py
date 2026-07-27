from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from app.services.data_service import (
    get_dashboard_stats,
    get_recent_crawlers,
    get_crawler_logs,
)
from app.routes.dependencies import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/crawlers")
async def read_crawlers(request: Request, user=Depends(get_current_user)):
    stats = get_dashboard_stats()
    crawlers = get_recent_crawlers(1000)
    return templates.TemplateResponse(
        request=request,
        name="crawlers.html",
        context={"crawlers": crawlers, "stats": stats, "active_page": "crawlers"},
    )


@router.get("/api/crawlers/{uid}/logs")
async def api_crawler_logs(uid: str, user=Depends(get_current_user)):
    return {"logs": get_crawler_logs(uid)}
