
from app.db import user_db, user_logs_db, user_bugs_db
from app.libs.exceptions import ConflictException, BadRequestException
from app.models.user_model import UserCreate
from fastapi.responses import JSONResponse
from pymongo import ReturnDocument
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.utils.pushover import sendPushOver
import uuid

def create_user(user: UserCreate):
    user_dict = user.model_dump()
    
    existing_user = user_db.find_one({"email": user_dict["email"]})
    if existing_user:
        raise ConflictException("User with this email already exists")
    
    user_dict['uid'] = str(uuid.uuid4())
    user_dict['device_list'] = []
    user_dict['role'] = "user"
    user_db.insert_one(user_dict)
    
    return JSONResponse(
        status_code=201
    )

def get_all_users():
    users = list(user_db.find({}, {"_id": 0}))
    return JSONResponse(
        status_code=200,
        content={"message": "Users retrieved", "data": users},
    )

def get_all_admins():
    admins = list(user_db.find({"role": "admin"}, {"_id": 0}))
    return admins

def delete_user(userUid: str):
    result = user_db.delete_one({"uid": userUid})
    if not result.deleted_count > 0:
        raise BadRequestException("User not found")
    else:
        return JSONResponse(
            status_code=200,
            content={"message": "User deleted"},
        )
        
def log_user(userUid: str, message: str):
    kst = ZoneInfo("Asia/Seoul")
    now_kst = datetime.now(kst)
    
    log_entry = {
        "uid": userUid,
        "datetime": now_kst,
        "datetime_kst": now_kst.strftime("%Y-%m-%d %H:%M:%S"),
        "message": message
    }

    user_logs_db.insert_one(log_entry)

def bug_user(userUid: str, message: str):
    kst = ZoneInfo("Asia/Seoul")
    now_kst = datetime.now(kst)
    
    log_entry = {
        "uid": userUid,
        "datetime": now_kst,
        "datetime_kst": now_kst.strftime("%Y-%m-%d %H:%M:%S"),
        "message": message
    }

    user_bugs_db.insert_one(log_entry)
    
def update_user_version(userUid: str, oldVersionName: str | None, newVersionName: str):
    updated_user = user_db.find_one_and_update(
        {"uid": userUid},
        {"$set": {"version": newVersionName}},
        return_document=ReturnDocument.AFTER
    )
    if not updated_user:
        raise BadRequestException("User not found")
    
    if oldVersionName:
        userName = updated_user.get("name", "Unknown")
        msg = f"{userName} updated {oldVersionName} -> {newVersionName}"
        sendPushOver(msg, [admin['pushoverKey'] for admin in get_all_admins()])
        log_user(userUid, f"Updated version: {oldVersionName} -> {newVersionName}")
    
    return JSONResponse(
        status_code=200,
        content={"message": "User version updated"},
    )