
from app.db import user_db, user_logs_db, user_bugs_db
from app.libs.exceptions import ConflictException, BadRequestException
from app.models.user_model import UserCreate
from app.utils.mongo import clean_doc
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
        status_code=201,
        content={"message": "User created", "data": clean_doc(user_dict)},
    )

def get_all_users():
    users = user_db.find()
    user_list = [clean_doc(user) for user in users]
    return JSONResponse(
        status_code=200,
        content={"message": "Users retrieved", "data": user_list},
    )

def get_all_admins():
    admins = user_db.find({"role": "admin"})
    admin_list = [clean_doc(admin) for admin in admins]
    return admin_list

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
        content={"message": "User version updated", "data": clean_doc(updated_user)},
    )