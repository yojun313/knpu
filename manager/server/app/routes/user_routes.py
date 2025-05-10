from fastapi import APIRouter, Depends, Body
from app.models.user_model import UserCreate
from app.services.user_service import create_user, delete_user, get_all_users, log_user, bug_user
from app.libs.jwt import verify_token
from starlette.background import BackgroundTask
from fastapi.responses import JSONResponse


router = APIRouter()

@router.post("/add")
def addUser(user: UserCreate):
    return create_user(user)

@router.post("/log")
def addUserLog(message: str = Body(..., embed=True), userUid = Depends(verify_token)):
    task = BackgroundTask(log_user, userUid, message)
    return JSONResponse(
        status_code=201, 
        content={"message": "User log added"},
        background=task
    )

@router.post("/bug")
def addUserBug(message: str = Body(..., embed=True), userUid = Depends(verify_token)):
    return bug_user(userUid, message)

@router.get("")
def loadUsers():
    return get_all_users()

@router.delete("/{userUid}")
def deleteUser(userUid: str):
    return delete_user(userUid)
