from fastapi import APIRouter, Depends, Body
from app.services.user_service import (
    get_all_users,
    log_user,
    bug_user,
    get_all_admins,
    update_user_version,
)
from app.libs.jwt import verify_token
from starlette.background import BackgroundTask
from fastapi.responses import JSONResponse
from app.libs.discord_notify import notify_discord


router = APIRouter()


@router.post("/log")
def addUserLog(message: str = Body(..., embed=True), userUid=Depends(verify_token)):
    task = BackgroundTask(log_user, userUid, "manager.client.custom_log", message)
    return JSONResponse(
        status_code=201, content={"message": "User log added"}, background=task
    )


@router.post("/bug")
def addUserBug(message: str = Body(..., embed=True), userUid=Depends(verify_token)):
    return bug_user(userUid, message)


@router.post("/version")
def updateVersion(
    oldVersionName: str | None = Body(None, embed=True),
    newVersionName: str = Body(..., embed=True),
    userUid=Depends(verify_token),
):
    return update_user_version(userUid, oldVersionName, newVersionName)


@router.get("")
def loadUsers():
    return get_all_users()


@router.get("/admin/list")
def loadAdminUsers():
    admin_list = get_all_admins()
    return JSONResponse(
        status_code=200,
        content={"message": "Admins retrieved", "data": admin_list},
    )


@router.post("/admin/notify")
def sendAdminNotify(
    message: str = Body(..., embed=True), kind: str = Body("ops", embed=True)
):
    channel_key = "system_error" if kind == "error" else "admin_ops"
    notify_discord(channel_key, message)
    return JSONResponse(
        status_code=200,
        content={"message": "Notification sent to admin"},
    )
