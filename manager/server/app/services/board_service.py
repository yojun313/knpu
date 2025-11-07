import uuid
from datetime import datetime, timezone, timedelta
from fastapi.responses import JSONResponse
from app.db import version_board_db, bug_board_db, free_board_db, user_db, user_bugs_db
from app.models.board_model import AddVersionDto, AddBugDto, AddPostDto
from app.utils.mongo import clean_doc
from app.utils.pushover import sendPushOver
from app.libs.exceptions import NotFoundException
from dotenv import load_dotenv
import pytz
import os
from starlette.background import BackgroundTask
from zoneinfo import ZoneInfo


load_dotenv()

# ----------- Version Board -----------


def add_version(data: AddVersionDto):
    doc = data.model_dump()
    doc["uid"] = str(uuid.uuid4())
    doc["releaseDate"] = datetime.now(
        ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")

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
        pushover_keys = [doc["pushoverKey"]
                         for doc in keys if doc["pushoverKey"] != 'n']
        for key in pushover_keys:
            msg = (
                "[ New Version Released! ]\n\n"
                f"Version Num: {doc["versionName"]}\n"
                f"Release Date: {doc["releaseDate"]}\n"
                f"ChangeLog: {doc["changeLog"]}\n"
                f"Version Features: {doc["features"]}\n"
                f"Version Detail: \n{doc["details"]}\n"
            )
            sendPushOver(msg, key)


def get_version(versionName: str):
    doc = version_board_db.find_one({"versionName": versionName})
    if not doc:
        # 임시 JSON 데이터 생성
        temp_doc = {
            "versionName": versionName,
            "releaseDate": "",
            "changeLog": "",
            "features": "",
            "details": "",
            "uid": str(uuid.uuid4())
        }
        return JSONResponse(status_code=200, content={"message": "Version not found, returning temporary data", "data": temp_doc})
    
    return JSONResponse(status_code=200, content={"message": "Version post retrieved", "data": clean_doc(doc)})


def get_version_list():
    docs = [clean_doc(d) for d in version_board_db.find()]
    return JSONResponse(status_code=200, content={"message": "Version list retrieved", "data": docs})


def delete_version(versionName: str):
    result = version_board_db.delete_one({"versionName": versionName})
    if result.deleted_count == 0:
        raise NotFoundException("Version not found")
    return JSONResponse(status_code=200, content={"message": "Version post deleted"})


def check_newest_version():
    def sort_by_version(two_dim_list):
        # 버전 번호를 파싱하여 비교하는 함수
        def version_key(version_str):
            return [int(part) for part in version_str.split('.')]

        sorted_list = sorted(
            two_dim_list, key=lambda x: version_key(x[0]), reverse=True)
        return sorted_list

    docs = version_board_db.find()
    docs_list = [clean_doc(d) for d in docs]
    version_data = sort_by_version(
        [list(map(str, item.values())) for item in docs_list])
    newest_version = version_data[0]
    return JSONResponse(status_code=200, content={"message": "Newest version retrieved", "data": newest_version})

# ----------- Bug Board -----------


def add_bug(data: AddBugDto):
    doc = data.model_dump()
    writer = user_db.find_one({"uid": doc["writerUid"]})
    writerDoc = clean_doc(writer)

    # 오늘 날짜의 버그 로그 불러오기
    today_key = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")
    bug_doc = user_bugs_db.find_one(
        {"uid": doc["writerUid"]}, {today_key: 1, "_id": 0})

    doc["uid"] = str(uuid.uuid4())
    doc["datetime"] = datetime.now(timezone.utc)
    doc['writerName'] = writerDoc['name']
    if bug_doc and today_key in bug_doc:
        messages = [entry["message"] for entry in bug_doc[today_key]]
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
        f"Datetime: {doc['datetime']}\n"
        f"Detail: \n{doc['bugText']}\n"
        f"log: \n\n{doc['programLog']}\n"
    )
    sendPushOver(msg, os.getenv("ADMIN_PUSHOVER"))

    return JSONResponse(status_code=201, content={"message": "Bug post created", "data": clean_doc(doc)})


def get_bug(uid: str):
    doc = bug_board_db.find_one({"uid": uid})
    if not doc:
        raise NotFoundException("Bug post not found")

    return JSONResponse(status_code=200, content={"message": "Bug post retrieved", "data": clean_doc(doc)})


def get_bug_list():
    docs = []

    for doc in bug_board_db.find().sort("datetime", -1):
        doc = clean_doc(doc)
        docs.append(doc)

    return JSONResponse(status_code=200, content={"message": "Bug list retrieved", "data": docs})


def delete_bug(uid: str):
    result = bug_board_db.delete_one({"uid": uid})
    if result.deleted_count == 0:
        raise NotFoundException("Bug post not found")
    return JSONResponse(status_code=200, content={"message": "Bug post deleted"})

# ----------- Free Board -----------


def add_post(data: AddPostDto):
    doc = data.model_dump()
    doc["uid"] = str(uuid.uuid4())
    doc["datetime"] = datetime.now(timezone.utc)
    doc['writerName'] = user_db.find_one({"uid": doc["writerUid"]})['name']
    doc["viewCnt"] = 0
    free_board_db.insert_one(doc)
    doc["datetime"] = datetime.now(timezone.utc)

    if doc['sendPushOver']:
        keys = list(user_db.find({}, {"pushoverKey": 1, "_id": 0}))
        pushover_keys = [doc["pushoverKey"]
                         for doc in keys if doc["pushoverKey"] != 'n']
        for key in pushover_keys:
            msg = (
                "[ New Post Added! ]\n"
                f"User: {doc['writerName']}\n"
                f"Post Title: {doc['title']}\n"
                f"Post Date: {doc['datetime']}\n"
                f"Post Text: {doc['text']}\n"
            )
            sendPushOver(msg, key)

    return JSONResponse(status_code=201, content={"message": "Post added", "data": clean_doc(doc)})


def get_post(uid: str):

    doc = free_board_db.find_one_and_update(
        {"uid": uid},
        {"$inc": {"viewCnt": 1}
         }, return_document=True)

    if not doc:
        raise NotFoundException("Post not found")

    return JSONResponse(status_code=200, content={"message": "Post retrieved", "data": clean_doc(doc)})


def get_post_list():
    docs = []

    for doc in free_board_db.find().sort("datetime", -1):
        doc = clean_doc(doc)
        docs.append(doc)

    return JSONResponse(status_code=200, content={"message": "post list retrieved", "data": docs})


def delete_post(uid: str):
    result = free_board_db.delete_one({"uid": uid})
    if result.deleted_count == 0:
        raise NotFoundException("Post not found")
    return JSONResponse(status_code=200, content={"message": "Post deleted"})


def edit_post(postUid: str, data: AddPostDto):
    update_fields = data.model_dump()

    result = free_board_db.update_one(
        {"uid": postUid},
        {"$set": update_fields}
    )

    if result.matched_count == 0:
        raise NotFoundException("Post not found")

    updated_doc = free_board_db.find_one({"uid": postUid})
    updated_doc['datetime'] = updated_doc['datetime'].astimezone(
        pytz.timezone("Asia/Seoul")).strftime("%m-%d %H:%M")
    return JSONResponse(
        status_code=200,
        content={"message": "Post updated", "data": clean_doc(updated_doc)},
    )
