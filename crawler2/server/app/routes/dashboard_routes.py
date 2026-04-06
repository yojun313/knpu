import os
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=TEMPLATE_DIR)


@router.get("/")
async def dashboard_page(request: Request):
    user = getattr(request.state, "user", None)
    username = user.get("name", "") if user else ""
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "username": username,
        }
    )
