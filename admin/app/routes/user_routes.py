from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from app.services.data_service import get_all_users
from app.routes.dependencies import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/users")
async def read_users(request: Request, user=Depends(get_current_user)):
    users = get_all_users()
    return templates.TemplateResponse(
        request=request,
        name="users.html",
        context={
            "users": users, 
            "active_page": "users"
        }
    )