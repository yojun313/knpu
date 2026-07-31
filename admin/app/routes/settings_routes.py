from fastapi import APIRouter, Body, Depends, Request
from fastapi.templating import Jinja2Templates
from app.routes.dependencies import get_current_user
from app.services import settings_service

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["get_nav_items"] = settings_service.get_nav_items_ordered


@router.get("/settings")
async def settings_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse(
        request=request, name="settings.html", context={"active_page": "settings"}
    )


@router.get("/api/nav-order")
async def api_get_nav_order(user=Depends(get_current_user)):
    return {"items": settings_service.get_nav_items_ordered()}


@router.post("/api/nav-order")
async def api_save_nav_order(
    order: list[str] = Body(..., embed=True), user=Depends(get_current_user)
):
    items = settings_service.save_nav_order(order)
    return {"items": items}
