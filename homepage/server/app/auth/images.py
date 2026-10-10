"""Uploaded objects are isolated per authenticated owner."""

import hashlib
from fastapi import HTTPException
from app.db import members_db, news_db, gallery_db, popup_db
from app.libs.r2 import PUBLIC_BASE


def image_prefix(user):
    owner = hashlib.sha256(user["sub"].encode()).hexdigest()
    return f"uploads/{owner}/"


def can_delete_image(key, user):
    if user.get("role") == "admin":
        return True
    if not key.startswith(image_prefix(user)):
        return False
    url = f"{PUBLIC_BASE}/{key}"
    # A user's image may also have been reused by another author or in legacy content.
    for collection, field in [
        (members_db, "image"),
        (news_db, "image"),
        (gallery_db, "photos"),
        (popup_db, "image"),
    ]:
        if collection.find_one({field: url, "created_by": {"$ne": user["sub"]}}):
            return False
    return True


def require_image_owner(key, user):
    if not can_delete_image(key, user):
        raise HTTPException(
            status_code=403,
            detail="본인이 업로드한 이미지 중 다른 작성자의 콘텐츠에 사용되지 않는 이미지만 삭제할 수 있습니다.",
        )
