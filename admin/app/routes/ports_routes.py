from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from app.services.ports_service import PortsService
from app.routes.dependencies import get_current_user

router = APIRouter(prefix="/ports", tags=["ports"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def ports_page(request: Request, user=Depends(get_current_user)):
    ports, dangling = PortsService.get_listening_ports()
    return templates.TemplateResponse(
        request=request,
        name="ports.html",
        context={"ports": ports, "dangling": dangling, "active_page": "ports"},
    )


@router.get("/status")
async def ports_status(user=Depends(get_current_user)):
    ports, dangling = PortsService.get_listening_ports()
    return {"ports": ports, "dangling": dangling}
