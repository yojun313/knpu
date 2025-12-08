from fastapi import APIRouter, Query, Header
from app.services.auth_service import request_verify, verify_code, loginWithToken

router = APIRouter()

@router.get("/request")
def request_verification(name: str = Query(..., description="유저 이름")):
    return request_verify(name)

@router.post("/verify")
def verify_user(name: str = Query(...), code: str = Query(...), device: str = Query(...)):
    return verify_code(name, code, device)

@router.get("/login")
def login_with_token(Authorization: str = Header(...)):
    token = Authorization.replace("Bearer ", "")
    return loginWithToken(token)
