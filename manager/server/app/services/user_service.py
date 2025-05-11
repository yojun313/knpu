
from app.db import user_db, user_logs_db, user_bugs_db
from app.libs.exceptions import ConflictException, BadRequestException
from app.models.user_model import UserCreate
from app.utils.mongo import clean_doc
from fastapi.responses import JSONResponse
from datetime import datetime
from zoneinfo import ZoneInfo
import uuid

def create_user(user: UserCreate):
    user_dict = user.model_dump()
    
    existing_user = user_db.find_one({"email": user_dict["email"]})
    if existing_user:
        raise ConflictException("User with this email already exists")
    
    user_dict['uid'] = str(uuid.uuid4())
    user_dict['device_list'] = []
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
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    date_key = now_kst.strftime("%Y-%m-%d")
    time_str = now_kst.strftime("%H:%M:%S")

    log_entry = {
        "time": time_str,
        "message": message
    }

    user_logs_db.update_one(
        {"uid": userUid},
        {"$push": {date_key: log_entry}, "$setOnInsert": {"uid": userUid}},
        upsert=True
    )

def bug_user(userUid: str, message: str):
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    date_key = now_kst.strftime("%Y-%m-%d")
    time_str = now_kst.strftime("%H:%M:%S")

    log_entry = {
        "time": time_str,
        "message": message
    }

    user_bugs_db.update_one(
        {"uid": userUid},
        {"$push": {date_key: log_entry}, "$setOnInsert": {"uid": userUid}},
        upsert=True
    )
