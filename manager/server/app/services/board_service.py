import uuid
from datetime import datetime, timezone, timedelta
from fastapi.responses import JSONResponse
from app.db import version_board_db, bug_board_db, free_board_db, user_db, user_bugs_db
from app.models.board_model import AddVersionDto, AddBugDto, AddPostDto
from app.utils.mongo import clean_doc
from app.utils.pushover import sendPushOver
from app.libs.exceptions import NotFoundException
from dotenv import load_dotenv
import os
from starlette.background import BackgroundTask
from zoneinfo import ZoneInfo
from app.services.user_service import log_user
import re

load_dotenv()

def _version_key(doc):
    ver = doc.get('versionName', '')
    nums = re.findall(r"\d+", ver)
    try:
        return tuple(int(x) for x in nums) if nums else ()
    except Exception:
        return ()

def add_version(data: AddVersionDto, userUid: str):
    log_user(userUid, f"Added new version: {data.versionName}")
    doc = data.model_dump()
    doc["uid"] = str(uuid.uuid4())
    
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    doc["releaseDate"] = now_kst.strftime("%Y-%m-%d")
    doc["datetime"] = now_kst
    doc["datetime_kst"] = now_kst.strftime("%Y-%m-%d %H:%M:%S")
    doc['publisher'] = userUid

    version_board_db.insert_one(doc)

    task = BackgroundTask(add_version_bg, doc)
    return JSONResponse(
        status_code=201,
        content={"message": "Version post created", "data": clean_doc(doc)},
        background=task
    )

def add_version_bg(doc):
    if doc['sendPushOver']:
        keys = list(user_db.find({}, {"pushoverKey": 1, "_id": 0}))
        pushover_keys = [k["pushoverKey"] for k in keys if k["pushoverKey"] != 'n']
        msg = (
            "[ New Version Released! ]\n\n"
            f"Version Num: {doc['versionName']}\n"
            f"Release Date: {doc['releaseDate']}\n"
            f"ChangeLog: {doc['changeLog']}\n"
            f"Version Features: {doc['features']}\n"
            f"Version Detail: \n{doc['details']}\n"
        )
        sendPushOver(msg, pushover_keys)

def get_version(versionName: str):
    doc = version_board_db.find_one({"versionName": versionName})
    if not doc:
        temp_doc = {
            "versionName": versionName,
            "releaseDate": "",
            "changeLog": "",
            "features": "",
            "details": "",
            "uid": str(uuid.uuid4()),
            "publisher": "Unknown",
            "fullUpdate": False,
        }
        return JSONResponse(status_code=200, content={"message": "Version not found, returning temporary data", "data": temp_doc})
    
    publisher_doc = user_db.find_one({"uid": doc['publisher']}, {"name": 1, "_id": 0})
    doc['publisher'] = publisher_doc['name'] if publisher_doc else "Unknown"
    
    return JSONResponse(status_code=200, content={"message": "Version post retrieved", "data": clean_doc(doc)})

def edit_version(versionName: str, data: AddVersionDto, userUid: str):
    log_user(userUid, f"Edited version: {versionName}")
    update_fields = data.model_dump()
    update_fields['releaseDate'] = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")

    version_board_db.update_one(
        {"versionName": versionName},
        {"$set": update_fields}
    )

    return JSONResponse(
        status_code=200,
        content={"message": "Version updated"},
    )
    
def get_version_list():
    docs = [clean_doc(d) for d in version_board_db.find()]
    docs.sort(key=_version_key, reverse=True)

    for doc in docs:
        publisher_info = user_db.find_one({"uid": doc['publisher']}, {"name": 1, "_id": 0})
        doc['publisher'] = publisher_info['name'] if publisher_info else "Unknown"

    return JSONResponse(status_code=200, content={"message": "Version list retrieved", "data": docs})

def delete_version(versionName: str, userUid: str):
    log_user(userUid, f"Deleted version: {versionName}")
    result = version_board_db.delete_one({"versionName": versionName})
    if result.deleted_count == 0:
        raise NotFoundException("Version not found")
    return JSONResponse(status_code=200, content={"message": "Version post deleted"})

def check_newest_version():
    docs = [clean_doc(d) for d in version_board_db.find()]
    if not docs:
        return JSONResponse(status_code=200, content={"message": "Newest version retrieved", "data": []})

    docs.sort(key=_version_key, reverse=True)
    newest_version = [docs[0].get('versionName')]
    return JSONResponse(status_code=200, content={"message": "Newest version retrieved", "data": newest_version})

def add_bug(data: AddBugDto, userUid: str):
    log_user(userUid, f"Added new bug: {data.bugTitle}")
    doc = data.model_dump()
    writer = user_db.find_one({"uid": doc["writerUid"]})
    writerDoc = clean_doc(writer)

    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    start_of_day = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    bug_logs = list(user_bugs_db.find({
        "uid": doc["writerUid"],
        "datetime": {"$gte": start_of_day, "$lt": end_of_day}
    }).sort("datetime", 1))

    doc["uid"] = str(uuid.uuid4())
    doc["datetime"] = now_kst
    doc["datetime_kst"] = now_kst.strftime("%Y-%m-%d %H:%M:%S")
    doc['writerName'] = writerDoc['name']

    if bug_logs:
        messages = [f"[{b.get('datetime_kst', '')}] {b.get('message', '')}" for b in bug_logs]
        doc["programLog"] = "\n".join(messages)
    else:
        doc["programLog"] = "(No program logs for today)"

    bug_board_db.insert_one(doc)

    doc = clean_doc(doc)
    msg = (
        "[ New Bug Added! ]\n"
        f"User: {writerDoc['name']}\n"
        f"Version: {doc['versionName']}\n"
        f"Title: {doc['bugTitle']}\n"
        f"Datetime: {doc['datetime_kst']}\n"
        f"Detail: \n{doc['bugText']}\n"
        f"log: \n\n{doc['programLog']}\n"
    )
    sendPushOver(msg, [os.getenv("ADMIN_PUSHOVER")])

    return JSONResponse(status_code=201, content={"message": "Bug post created", "data": clean_doc(doc)})

def get_bug(uid: str, userUid: str):
    doc = bug_board_db.find_one({"uid": uid})
    if not doc:
        raise NotFoundException("Bug post not found")

    log_user(userUid, f"Viewed bug: {doc['bugTitle']}")
    
    return JSONResponse(status_code=200, content={"message": "Bug post retrieved", "data": clean_doc(doc)})

def get_bug_list():
    docs = []

    for doc in bug_board_db.find().sort("datetime", -1):
        doc = clean_doc(doc)
        docs.append(doc)

    return JSONResponse(status_code=200, content={"message": "Bug list retrieved", "data": docs})

def delete_bug(uid: str, userUid: str):
    log_user(userUid, f"Deleted bug with UID: {uid}")
    result = bug_board_db.delete_one({"uid": uid})
    if result.deleted_count == 0:
        raise NotFoundException("Bug post not found")
    return JSONResponse(status_code=200, content={"message": "Bug post deleted"})

def add_post(data: AddPostDto, userUid: str):
    doc = data.model_dump()
    
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    doc["uid"] = str(uuid.uuid4())
    doc["datetime"] = now_kst
    doc["datetime_kst"] = now_kst.strftime("%Y-%m-%d %H:%M:%S")
    doc['writerName'] = user_db.find_one({"uid": doc["writerUid"]})['name']
    doc["viewCnt"] = []
    
    free_board_db.insert_one(doc)

    if doc['sendPushOver']:
        keys = list(user_db.find({}, {"pushoverKey": 1, "_id": 0}))
        pushover_keys = [k["pushoverKey"] for k in keys if k["pushoverKey"] != 'n']
        msg = (
            "[ New Post Added! ]\n"
            f"User: {doc['writerName']}\n"
            f"Post Title: {doc['title']}\n"
            f"Post Date: {doc['datetime_kst']}\n"
            f"Post Text: {doc['text']}\n"
        )
        sendPushOver(msg, pushover_keys)
        
    log_user(userUid, f"Added new post: {data.title}")

    return JSONResponse(status_code=201, content={"message": "Post added", "data": clean_doc(doc)})

def get_post(uid: str, userUid: str):
    doc = free_board_db.find_one_and_update(
        {"uid": uid},
        {"$addToSet": {"viewCnt": userUid}}, 
        return_document=True
    )

    if not doc: 
        raise NotFoundException("Post not found")

    log_user(userUid, f"Viewed post: {doc['title']}")
    return JSONResponse(status_code=200, content={"message": "Post retrieved", "data": clean_doc(doc)})

def get_post_list():
    docs = []

    for doc in free_board_db.find().sort("datetime", -1):
        doc = clean_doc(doc)
        doc['viewCnt'] = len(doc['viewCnt'])   
        docs.append(doc)

    return JSONResponse(status_code=200, content={"message": "post list retrieved", "data": docs})

def delete_post(uid: str, userUid: str):
    log_user(userUid, f"Deleted post with UID: {uid}")
    result = free_board_db.delete_one({"uid": uid})
    if result.deleted_count == 0:
        raise NotFoundException("Post not found")
    return JSONResponse(status_code=200, content={"message": "Post deleted"})

def edit_post(postUid: str, data: AddPostDto, userUid: str):
    log_user(userUid, f"Edited post with UID: {postUid}")
    update_fields = data.model_dump()

    result = free_board_db.update_one(
        {"uid": postUid},
        {"$set": update_fields}
    )

    if result.matched_count == 0:
        raise NotFoundException("Post not found")

    updated_doc = free_board_db.find_one({"uid": postUid})
    updated_doc['datetime'] = updated_doc.get('datetime_kst', '')
    return JSONResponse(
        status_code=200,
        content={"message": "Post updated", "data": clean_doc(updated_doc)},
    )