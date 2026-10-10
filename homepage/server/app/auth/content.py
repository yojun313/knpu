"""Homepage content ownership. Records without an owner remain admin managed."""

import uuid
from fastapi import HTTPException

OWNER = "created_by"


def require_content_owner(doc, user):
    if doc is None:
        raise HTTPException(status_code=404, detail="콘텐츠를 찾을 수 없습니다")
    if user.get("role") != "admin" and (
        not doc.get(OWNER) or doc[OWNER] != user["sub"]
    ):
        raise HTTPException(
            status_code=403,
            detail="본인이 추가한 콘텐츠만 수정·삭제할 수 있습니다.",
        )
    return doc


def content_filter(collection, uid, user):
    doc = require_content_owner(collection.find_one({"uid": uid}), user)
    query = {"_id": doc["_id"]}
    if user.get("role") != "admin":
        query[OWNER] = user["sub"]
    return query


def check_content_update(collection, data, user):
    if data.get("uid"):
        doc = collection.find_one({"uid": data["uid"]})
        if doc:
            require_content_owner(doc, user)


def save_content(collection, data, user):
    data.pop(OWNER, None)  # Never accept ownership from a client.
    doc = collection.find_one({"uid": data.get("uid")}) if data.get("uid") else None
    if doc:
        query = content_filter(collection, data["uid"], user)
        result = collection.update_one(query, {"$set": data})
        if not result.matched_count:
            raise HTTPException(
                status_code=409,
                detail="콘텐츠가 변경되었습니다. 목록을 새로고침해주세요.",
            )
        if doc.get(OWNER):
            data[OWNER] = doc[OWNER]
    else:
        # Always use a fresh server UUID, including clients that generate their own UUID.
        data["uid"] = str(uuid.uuid4())
        data[OWNER] = user["sub"]
        collection.insert_one(dict(data))
    return data


def delete_content(collection, uid, user):
    result = collection.delete_one(content_filter(collection, uid, user))
    if not result.deleted_count:
        raise HTTPException(
            status_code=409, detail="콘텐츠가 변경되었습니다. 목록을 새로고침해주세요."
        )
    return result
