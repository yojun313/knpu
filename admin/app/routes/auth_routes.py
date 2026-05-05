from fastapi import APIRouter, Request, Form, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from app.services.auth_service import request_login, verify_login
from datetime import datetime, timedelta

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={}
    )

@router.post("/login")
async def handle_login(request: Request, name: str = Form(...)):
    email = request_login(name) 
    if not email:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "관리자 권한이 없거나 등록되지 않은 이름입니다."
            }
        )    
    response = RedirectResponse(url=f"/verify?name={name}", status_code=302)
    return response

@router.get("/verify")
async def verify_page(request: Request, name: str):
    return templates.TemplateResponse(
        request=request,
        name="verify.html",
        context={"name": name}
    )

@router.post("/verify")
async def handle_verify(response: Response, name: str = Form(...), code: str = Form(...)):
    session_id = verify_login(name, code)
    if not session_id:
        return RedirectResponse(url=f"/verify?name={name}&error=invalid", status_code=302)
    
    res = RedirectResponse(url="/", status_code=302)
    
    res.set_cookie(
        key="session_id", 
        value=session_id, 
        httponly=True, 
        max_age=60*60*24*30,
        samesite="lax",       
        path="/"              
    )
    return res