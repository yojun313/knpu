from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from app.routes.dependencies import get_current_user
from app.services import claude_usage_service, claude_account_usage_service

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/claude-usage")
async def claude_usage_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse(
        request=request,
        name="claude_usage.html",
        context={"active_page": "claude_usage"},
    )


@router.get("/api/claude-usage")
async def api_claude_usage(user=Depends(get_current_user)):
    data = claude_usage_service.compute_usage()
    data["account"] = claude_account_usage_service.get_account_usage()
    return data
