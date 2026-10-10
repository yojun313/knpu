import uuid
from datetime import datetime, timezone, timedelta
from fastapi.responses import JSONResponse
from app.db import version_board_db, bug_board_db, free_board_db, user_db, user_bugs_db
from app.models.board_model import AddVersionDto, AddBugDto, AddPostDto
from system.notify.discord import notify_discord
from app.libs.exceptions import NotFoundException
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
from app.services.user_service import log_user
import re
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder


def _require_admin(uid: str):
    user = user_db.find_one({"uid": uid}, {"role": 1, "name": 1})
    if not user or user.get("role") != "admin":
        raise HTTPException(403, "관리자만 이 작업을 수행할 수 있습니다.")
    return user


def _editable_document(collection, query: dict, uid: str) -> dict:
    doc = collection.find_one(query, {"_id": 0})
    if not doc:
        raise NotFoundException("게시물을 찾을 수 없습니다.")
    user = user_db.find_one({"uid": uid}, {"role": 1})
    if doc.get("writerUid") != uid and (not user or user.get("role") != "admin"):
        raise HTTPException(403, "작성자 또는 관리자만 수정·삭제할 수 있습니다.")
    return doc


def _bug_for_user(
    doc: dict, uid: str, *, detail: bool = False, admin: bool | None = None
) -> dict:
    doc = dict(doc)
    if admin is None:
        user = user_db.find_one({"uid": uid}, {"role": 1})
        admin = bool(user and user.get("role") == "admin")
    if not detail or (not admin and doc.get("writerUid") != uid):
        doc.pop("programLog", None)
    doc["replies"] = [
        {
            **{k: v for k, v in reply.items() if k != "mail"},
            **(
                {"mailStatus": (reply.get("mail") or {}).get("status")} if admin else {}
            ),
        }
        for reply in doc.get("replies", [])
    ]
    doc["replyCount"] = len(doc["replies"])
    doc["datetime"] = doc.get("datetime_kst") or doc.get("datetime", "")
    return jsonable_encoder(doc)


load_dotenv()


def _version_key(doc):
    ver = doc.get("versionName", "")
    nums = re.findall(r"\d+", ver)
    try:
        return tuple(int(x) for x in nums) if nums else ()
    except Exception:
        return ()


def add_version(data: AddVersionDto, userUid: str):
    _require_admin(userUid)
    if version_board_db.find_one({"versionName": data.versionName}):
        raise HTTPException(409, "같은 버전의 패치 노트가 이미 있습니다.")
    log_user(
        userUid,
        "manager.version.create",
        f"Added new version: {data.versionName}",
        target={"type": "version", "id": data.versionName},
    )
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
    _require_admin(userUid)
    if data.versionName != versionName and version_board_db.find_one(
        {"versionName": data.versionName}
    ):
        raise HTTPException(409, "같은 버전의 패치 노트가 이미 있습니다.")
    log_user(
        userUid,
        "manager.version.update",
        f"Edited version: {versionName}",
        target={"type": "version", "id": versionName},
    )
    update_fields = data.model_dump()
    update_fields["releaseDate"] = datetime.now(ZoneInfo("Asia/Seoul")).strftime(
        "%Y-%m-%d"
    )

    result = version_board_db.update_one(
        {"versionName": versionName}, {"$set": update_fields}
    )
    if not result.matched_count:
        raise NotFoundException("Version not found")

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
    _require_admin(userUid)
    log_user(
        userUid,
        "manager.version.delete",
        f"Deleted version: {versionName}",
        target={"type": "version", "id": versionName},
    )
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
    log_user(
        userUid,
        "manager.bug.create",
        f"Added new bug: {data.bugTitle}",
        target={"type": "bug", "id": data.bugTitle},
    )
    doc = data.model_dump()
    doc["writerUid"] = userUid
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
    doc["replies"] = []

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
    notify_discord("system_error", msg)

    return JSONResponse(
        status_code=201,
        content={
            "message": "Bug post created",
            "data": _bug_for_user(doc, userUid, detail=True),
        },
    )


def get_bug(uid: str, userUid: str):
    doc = bug_board_db.find_one({"uid": uid}, {"_id": 0})
    if not doc:
        raise NotFoundException("Bug post not found")

    doc["datetime"] = doc.get("datetime_kst", "")
    log_user(
        userUid,
        "manager.bug.view",
        f"Viewed bug: {doc['bugTitle']}",
        target={"type": "bug", "id": doc["bugTitle"]},
    )

    return JSONResponse(
        status_code=200,
        content={
            "message": "Bug post retrieved",
            "data": _bug_for_user(doc, userUid, detail=True),
        },
    )


def get_bug_list(userUid: str):
    docs = list(bug_board_db.find({}, {"_id": 0}).sort("datetime", -1))

    for doc in docs:
        doc["datetime"] = doc.get("datetime_kst", "")

    user = user_db.find_one({"uid": userUid}, {"role": 1}) or {}
    return JSONResponse(
        status_code=200,
        content={
            "message": "Bug list retrieved",
            "data": [
                _bug_for_user(doc, userUid, admin=user.get("role") == "admin")
                for doc in docs
            ],
        },
    )


def delete_bug(uid: str, userUid: str):
    _editable_document(bug_board_db, {"uid": uid}, userUid)
    log_user(
        userUid,
        "manager.bug.delete",
        f"Deleted bug with UID: {uid}",
        target={"type": "bug", "id": uid},
    )
    result = bug_board_db.delete_one({"uid": uid})
    if result.deleted_count == 0:
        raise NotFoundException("Bug post not found")
    return JSONResponse(status_code=200, content={"message": "Bug post deleted"})


def add_post(data: AddPostDto, userUid: str):
    doc = data.model_dump()
    doc["writerUid"] = userUid
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

    log_user(
        userUid,
        "manager.post.create",
        f"Added new post: {data.title}",
        target={"type": "post", "id": data.title},
    )

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
    log_user(
        userUid,
        "manager.post.view",
        f"Viewed post: {doc['title']}",
        target={"type": "post", "id": doc["title"]},
    )
    return JSONResponse(
        status_code=200, content={"message": "Post retrieved", "data": doc}
    )


def get_post_list(userUid: str):
    docs = list(free_board_db.find({}, {"_id": 0}).sort("datetime", -1))

    for doc in docs:
        doc["readByMe"] = userUid in doc.get("viewCnt", [])
        doc["commentCount"] = len(doc.get("comments", []))
        doc["viewCnt"] = len(doc.get("viewCnt", []))
        doc["datetime"] = doc.get("datetime_kst", "")

    return JSONResponse(
        status_code=200, content={"message": "post list retrieved", "data": docs}
    )


def delete_post(uid: str, userUid: str):
    _editable_document(free_board_db, {"uid": uid}, userUid)
    log_user(
        userUid,
        "manager.post.delete",
        f"Deleted post with UID: {uid}",
        target={"type": "post", "id": uid},
    )
    result = free_board_db.delete_one({"uid": uid})
    if result.deleted_count == 0:
        raise NotFoundException("Post not found")
    return JSONResponse(status_code=200, content={"message": "Post deleted"})


def edit_post(postUid: str, data: AddPostDto, userUid: str):
    _editable_document(free_board_db, {"uid": postUid}, userUid)
    log_user(
        userUid,
        "manager.post.update",
        f"Edited post with UID: {postUid}",
        target={"type": "post", "id": postUid},
    )
    update_fields = data.model_dump()
    update_fields.pop("writerUid", None)

    result = free_board_db.update_one({"uid": postUid}, {"$set": update_fields})

    if result.matched_count == 0:
        raise NotFoundException("Post not found")

    updated_doc = free_board_db.find_one({"uid": postUid}, {"_id": 0})
    updated_doc["datetime"] = updated_doc.get("datetime_kst", "")

    return JSONResponse(
        status_code=200,
        content={"message": "Post updated", "data": updated_doc},
    )


def edit_bug(uid: str, data: AddBugDto, userUid: str):
    _editable_document(bug_board_db, {"uid": uid}, userUid)
    fields = {key: getattr(data, key) for key in ("versionName", "bugTitle", "bugText")}
    result = bug_board_db.update_one({"uid": uid}, {"$set": fields})
    if not result.matched_count:
        raise NotFoundException("Bug post not found")
    log_user(userUid, "manager.bug.update", f"Edited bug: {uid}")
    return get_bug(uid, userUid)


def add_bug_reply(uid: str, data, userUid: str):
    admin = _require_admin(userUid)
    now = datetime.now(timezone.utc)
    reply = {
        "uid": str(data.requestId),
        "writerUid": userUid,
        "writerName": admin.get("name") or "관리자",
        "text": data.text,
        "datetime": now.isoformat(),
        # Mail state is stored in the same atomic write as the reply.
        "mail": {"status": "pending", "attempts": 0, "next_attempt": now},
    }
    result = bug_board_db.update_one(
        {"uid": uid, "replies.uid": {"$ne": reply["uid"]}},
        {"$push": {"replies": reply}},
    )
    if not result.matched_count:
        existing = bug_board_db.find_one({"uid": uid}, {"replies": 1})
        if not existing:
            raise NotFoundException("Bug post not found")
        if not any(
            r.get("uid") == reply["uid"]
            and r.get("writerUid") == userUid
            and r.get("text") == data.text
            for r in existing.get("replies", [])
        ):
            raise HTTPException(409, "답변 요청이 충돌했습니다. 다시 시도해주세요.")
    else:
        log_user(userUid, "manager.bug.reply", f"Replied to bug: {uid}")
    return get_bug(uid, userUid)


def add_comment(uid: str, data, userUid: str):
    writer = user_db.find_one({"uid": userUid}, {"name": 1}) or {}
    comment = {
        "uid": str(data.requestId),
        "writerUid": userUid,
        "writerName": writer.get("name") or "사용자",
        "text": data.text,
        "datetime": datetime.now(timezone.utc).isoformat(),
    }
    result = free_board_db.update_one(
        {"uid": uid, "comments.uid": {"$ne": comment["uid"]}},
        {"$push": {"comments": comment}},
    )
    if not result.matched_count:
        existing = free_board_db.find_one({"uid": uid}, {"comments": 1})
        if not existing:
            raise NotFoundException("Post not found")
        if not any(
            c.get("uid") == comment["uid"]
            and c.get("writerUid") == userUid
            and c.get("text") == data.text
            for c in existing.get("comments", [])
        ):
            raise HTTPException(409, "댓글 요청이 충돌했습니다. 다시 시도해주세요.")
    else:
        log_user(userUid, "manager.post.comment.create", f"Commented on post: {uid}")
    return get_post(uid, userUid)


def _require_comment(uid: str, comment_uid: str, userUid: str):
    doc = free_board_db.find_one({"uid": uid}, {"comments": 1})
    comment = next(
        (c for c in (doc or {}).get("comments", []) if c.get("uid") == comment_uid),
        None,
    )
    if not comment:
        raise NotFoundException("댓글을 찾을 수 없습니다.")
    user = user_db.find_one({"uid": userUid}, {"role": 1}) or {}
    if comment.get("writerUid") != userUid and user.get("role") != "admin":
        raise HTTPException(403, "댓글 작성자 또는 관리자만 수정·삭제할 수 있습니다.")


def edit_comment(uid: str, comment_uid: str, data, userUid: str):
    _require_comment(uid, comment_uid, userUid)
    result = free_board_db.update_one(
        {"uid": uid, "comments.uid": comment_uid},
        {
            "$set": {
                "comments.$.text": data.text,
                "comments.$.editedAt": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    if not result.matched_count:
        raise NotFoundException("댓글을 찾을 수 없습니다.")
    log_user(userUid, "manager.post.comment.update", f"Edited comment: {comment_uid}")
    return get_post(uid, userUid)


def delete_comment(uid: str, comment_uid: str, userUid: str):
    _require_comment(uid, comment_uid, userUid)
    result = free_board_db.update_one(
        {"uid": uid, "comments.uid": comment_uid},
        {"$pull": {"comments": {"uid": comment_uid}}},
    )
    if not result.matched_count:
        raise NotFoundException("댓글을 찾을 수 없습니다.")
    log_user(userUid, "manager.post.comment.delete", f"Deleted comment: {comment_uid}")
    return get_post(uid, userUid)
