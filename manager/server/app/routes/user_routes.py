from fastapi import APIRouter, Depends, Body
from app.models.user_model import UserCreate
from app.services.user_service import create_user, delete_user, get_all_users, log_user, bug_user, get_all_admins, update_user_version
from app.libs.jwt import verify_token
from starlette.background import BackgroundTask
from fastapi.responses import JSONResponse
from app.utils.pushover import sendPushOver


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

@router.post('/version')
def updateVersion(
    oldVersionName: str | None = Body(None, embed=True), 
    newVersionName: str = Body(..., embed=True), 
    userUid = Depends(verify_token)
):
    return update_user_version(userUid, oldVersionName, newVersionName)

@router.get("")
def loadUsers():
    return get_all_users()

@router.delete("/{userUid}")
def deleteUser(userUid: str):
    return delete_user(userUid)

@router.get("/admin/list")
def loadAdminUsers():
    admin_list = get_all_admins()
    return JSONResponse(
        status_code=200,
        content={"message": "Admins retrieved", "data": admin_list},
    )
    
@router.post('/admin/pushover')
def sendAdminPushOver(message: str = Body(..., embed=True)):
    sendPushOver(message, [admin['pushoverKey'] for admin in get_all_admins()])
    return JSONResponse(
        status_code=200,
        content={"message": "PushOver sent to admin"},
    )