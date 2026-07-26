import uuid
from datetime import datetime, timezone, timedelta
from fastapi.responses import JSONResponse
from app.db import version_board_db, bug_board_db, free_board_db, user_db, user_bugs_db
from app.models.board_model import AddVersionDto, AddBugDto, AddPostDto
from app.libs.discord_notify import notify_discord
from app.libs.exceptions import NotFoundException
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
from app.services.user_service import log_user
import re

load_dotenv()


def _version_key(doc):
    ver = doc.get("versionName", "")
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
    doc["publisher"] = userUid

    version_board_db.insert_one(doc)

    # 새 버전은 예외 없이 항상 디스코드로 공지한다 (예전 pushover 방식의 "보낼지 말지" 확인은 없앰).
    embed = {
        "title": f"새 버전 배포: {data.versionName}",
        "color": 0x3B82F6,
        "fields": [
            {
                "name": "변경 사항",
                "value": (data.changeLog or "-")[:1024],
                "inline": False,
            },
            {
                "name": "주요 기능",
                "value": (data.features or "-")[:1024],
                "inline": False,
            },
            {
                "name": "상세 내용",
                "value": (data.details or "-")[:1024],
                "inline": False,
            },
            {
                "name": "전체 업데이트 여부",
                "value": "예" if data.fullUpdate else "아니오",
                "inline": True,
            },
            {"name": "배포일", "value": doc["releaseDate"], "inline": True},
        ],
    }
    notify_discord("manager_update", f"새 버전 배포: {data.versionName}", embed=embed)

    # JSON 직렬화를 위해 _id 제거 및 datetime 문자열 변환
    if "_id" in doc:
        del doc["_id"]
    doc["datetime"] = doc.get("datetime_kst", "")

    return JSONResponse(
        status_code=201,
        content={"message": "Version post created", "data": doc},
    )


def get_version(versionName: str):
    doc = version_board_db.find_one({"versionName": versionName}, {"_id": 0})
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
        return JSONResponse(
            status_code=200,
            content={
                "message": "Version not found, returning temporary data",
                "data": temp_doc,
            },
        )

    publisher_doc = user_db.find_one({"uid": doc["publisher"]}, {"name": 1, "_id": 0})
    doc["publisher"] = publisher_doc["name"] if publisher_doc else "Unknown"
    doc["datetime"] = doc.get("datetime_kst", "")

    return JSONResponse(
        status_code=200, content={"message": "Version post retrieved", "data": doc}
    )


def edit_version(versionName: str, data: AddVersionDto, userUid: str):
    log_user(userUid, f"Edited version: {versionName}")
    update_fields = data.model_dump()
    update_fields["releaseDate"] = datetime.now(ZoneInfo("Asia/Seoul")).strftime(
        "%Y-%m-%d"
    )

    version_board_db.update_one({"versionName": versionName}, {"$set": update_fields})

    return JSONResponse(
        status_code=200,
        content={"message": "Version updated"},
    )


def get_version_list():
    docs = list(version_board_db.find({}, {"_id": 0}))
    docs.sort(key=_version_key, reverse=True)

    for doc in docs:
        publisher_info = user_db.find_one(
            {"uid": doc["publisher"]}, {"name": 1, "_id": 0}
        )
        doc["publisher"] = publisher_info["name"] if publisher_info else "Unknown"
        doc["datetime"] = doc.get("datetime_kst", "")

    return JSONResponse(
        status_code=200, content={"message": "Version list retrieved", "data": docs}
    )


def delete_version(versionName: str, userUid: str):
    log_user(userUid, f"Deleted version: {versionName}")
    result = version_board_db.delete_one({"versionName": versionName})
    if result.deleted_count == 0:
        raise NotFoundException("Version not found")
    return JSONResponse(status_code=200, content={"message": "Version post deleted"})


def check_newest_version():
    docs = list(version_board_db.find({}, {"_id": 0}))
    if not docs:
        return JSONResponse(
            status_code=200, content={"message": "Newest version retrieved", "data": []}
        )

    docs.sort(key=_version_key, reverse=True)
    newest_version = [docs[0].get("versionName")]
    return JSONResponse(
        status_code=200,
        content={"message": "Newest version retrieved", "data": newest_version},
    )


def add_bug(data: AddBugDto, userUid: str):
    log_user(userUid, f"Added new bug: {data.bugTitle}")
    doc = data.model_dump()
    writer = user_db.find_one({"uid": doc["writerUid"]}, {"_id": 0})

    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    start_of_day = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    bug_logs = list(
        user_bugs_db.find(
            {
                "uid": doc["writerUid"],
                "datetime": {"$gte": start_of_day, "$lt": end_of_day},
            }
        ).sort("datetime", 1)
    )

    doc["uid"] = str(uuid.uuid4())
    doc["datetime"] = now_kst
    doc["datetime_kst"] = now_kst.strftime("%Y-%m-%d %H:%M:%S")
    doc["writerName"] = writer["name"] if writer else "Unknown"
    doc["notified"] = False

    if bug_logs:
        messages = [
            f"[{b.get('datetime_kst', '')}] {b.get('message', '')}" for b in bug_logs
        ]
        doc["programLog"] = "\n".join(messages)
    else:
        doc["programLog"] = "(No program logs for today)"

    bug_board_db.insert_one(doc)

    if "_id" in doc:
        del doc["_id"]
    doc["datetime"] = doc.get("datetime_kst", "")

    msg = (
        "[ New Bug Added! ]\n"
        f"User: {doc['writerName']}\n"
        f"Version: {doc['versionName']}\n"
        f"Title: {doc['bugTitle']}\n"
        f"Datetime: {doc['datetime_kst']}\n"
        f"Detail: \n{doc['bugText']}\n"
        f"log: \n\n{doc['programLog']}\n"
    )
    notify_discord("manager_error", msg)

    return JSONResponse(
        status_code=201, content={"message": "Bug post created", "data": doc}
    )


def get_bug(uid: str, userUid: str):
    doc = bug_board_db.find_one({"uid": uid}, {"_id": 0})
    if not doc:
        raise NotFoundException("Bug post not found")

    doc["datetime"] = doc.get("datetime_kst", "")
    log_user(userUid, f"Viewed bug: {doc['bugTitle']}")

    return JSONResponse(
        status_code=200, content={"message": "Bug post retrieved", "data": doc}
    )


def get_bug_list():
    docs = list(bug_board_db.find({}, {"_id": 0}).sort("datetime", -1))

    for doc in docs:
        doc["datetime"] = doc.get("datetime_kst", "")

    return JSONResponse(
        status_code=200, content={"message": "Bug list retrieved", "data": docs}
    )


def delete_bug(uid: str, userUid: str):
    log_user(userUid, f"Deleted bug with UID: {uid}")
    result = bug_board_db.delete_one({"uid": uid})
    if result.deleted_count == 0:
        raise NotFoundException("Bug post not found")
    return JSONResponse(status_code=200, content={"message": "Bug post deleted"})


def add_post(data: AddPostDto, userUid: str):
    doc = data.model_dump()
    doc["notified"] = False
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    doc["uid"] = str(uuid.uuid4())
    doc["datetime"] = now_kst
    doc["datetime_kst"] = now_kst.strftime("%Y-%m-%d %H:%M:%S")

    writer = user_db.find_one({"uid": doc["writerUid"]}, {"_id": 0})
    doc["writerName"] = writer["name"] if writer else "Unknown"
    doc["viewCnt"] = []

    free_board_db.insert_one(doc)

    if "_id" in doc:
        del doc["_id"]
    doc["datetime"] = doc.get("datetime_kst", "")

    if doc.get("broadcastNotify"):
        msg = (
            "[ New Post Added! ]\n"
            f"User: {doc['writerName']}\n"
            f"Post Title: {doc['title']}\n"
            f"Post Date: {doc['datetime_kst']}\n"
            f"Post Text: {doc['text']}\n"
        )
        notify_discord("announcements", msg)

    log_user(userUid, f"Added new post: {data.title}")

    return JSONResponse(status_code=201, content={"message": "Post added", "data": doc})


def get_post(uid: str, userUid: str):
    doc = free_board_db.find_one_and_update(
        {"uid": uid},
        {"$addToSet": {"viewCnt": userUid}},
        projection={"_id": 0},
        return_document=True,
    )

    if not doc:
        raise NotFoundException("Post not found")

    doc["datetime"] = doc.get("datetime_kst", "")
    log_user(userUid, f"Viewed post: {doc['title']}")
    return JSONResponse(
        status_code=200, content={"message": "Post retrieved", "data": doc}
    )


def get_post_list():
    docs = list(free_board_db.find({}, {"_id": 0}).sort("datetime", -1))

    for doc in docs:
        doc["viewCnt"] = len(doc.get("viewCnt", []))
        doc["datetime"] = doc.get("datetime_kst", "")

    return JSONResponse(
        status_code=200, content={"message": "post list retrieved", "data": docs}
    )


def delete_post(uid: str, userUid: str):
    log_user(userUid, f"Deleted post with UID: {uid}")
    result = free_board_db.delete_one({"uid": uid})
    if result.deleted_count == 0:
        raise NotFoundException("Post not found")
    return JSONResponse(status_code=200, content={"message": "Post deleted"})


def edit_post(postUid: str, data: AddPostDto, userUid: str):
    log_user(userUid, f"Edited post with UID: {postUid}")
    update_fields = data.model_dump()

    result = free_board_db.update_one({"uid": postUid}, {"$set": update_fields})

    if result.matched_count == 0:
        raise NotFoundException("Post not found")

    updated_doc = free_board_db.find_one({"uid": postUid}, {"_id": 0})
    updated_doc["datetime"] = updated_doc.get("datetime_kst", "")

    return JSONResponse(
        status_code=200,
        content={"message": "Post updated", "data": updated_doc},
    )
