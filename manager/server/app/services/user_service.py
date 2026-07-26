from app.db import user_db, user_logs_db, user_bugs_db
from app.libs.exceptions import BadRequestException
from fastapi.responses import JSONResponse
from pymongo import ReturnDocument
from datetime import datetime
from zoneinfo import ZoneInfo
from app.libs.discord_notify import notify_discord
import uuid


# password_hash·타임스탬프 등 클라이언트가 필요로 하지 않는(혹은 절대 노출되면 안 되는) 필드는
# 조회 시점에 프로젝션으로 걸러낸다.
_SAFE_PROJECTION = {
    "_id": 0,
    "password_hash": 0,
    "created_at": 0,
    "approved_at": 0,
    "approved_by": 0,
    "updated_at": 0,
}


def get_all_users():
    users = list(user_db.find({}, _SAFE_PROJECTION))
    return JSONResponse(
        status_code=200,
        content={"message": "Users retrieved", "data": users},
    )


def get_all_admins():
    admins = list(user_db.find({"role": "admin"}, _SAFE_PROJECTION))
    return admins


def log_user(userUid: str, message: str):
    kst = ZoneInfo("Asia/Seoul")
    now_kst = datetime.now(kst)

    log_entry = {
        "uid": str(uuid.uuid4()),
        "userUid": userUid,
        "datetime": now_kst,
        "datetime_kst": now_kst.strftime("%Y-%m-%d %H:%M:%S"),
        "message": message,
    }

    user_logs_db.insert_one(log_entry)


def bug_user(userUid: str, message: str):
    kst = ZoneInfo("Asia/Seoul")
    now_kst = datetime.now(kst)

    is_admin = user_db.find_one({"uid": userUid, "role": "admin"})
    if is_admin:
        status = "fixed"
        notified = True
    else:
        status = "pending"
        notified = False

    log_entry = {
        "uid": str(uuid.uuid4()),
        "userUid": userUid,
        "datetime": now_kst,
        "datetime_kst": now_kst.strftime("%Y-%m-%d %H:%M:%S"),
        "message": message,
        "notified": notified,
        "status": status,
    }

    user_bugs_db.insert_one(log_entry)


def update_user_version(userUid: str, oldVersionName: str | None, newVersionName: str):
    updated_user = user_db.find_one_and_update(
        {"uid": userUid},
        {"$set": {"version": newVersionName}},
        return_document=ReturnDocument.AFTER,
    )
    if not updated_user:
        raise BadRequestException("User not found")

    if oldVersionName:
        userName = updated_user.get("name", "Unknown")
        msg = f"{userName} updated {oldVersionName} -> {newVersionName}"
        notify_discord("admin_ops", msg)
        log_user(userUid, f"Updated version: {oldVersionName} -> {newVersionName}")

    return JSONResponse(
        status_code=200,
        content={"message": "User version updated"},
    )
