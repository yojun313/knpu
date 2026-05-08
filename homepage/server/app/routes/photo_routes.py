from fastapi import APIRouter, HTTPException, Query
from app.models import GroupPhoto
from app.db import gallery_db
import uuid
from datetime import datetime

router = APIRouter()


@router.get("/")
def list_group_photos():
    docs = list(gallery_db.find())
    for d in docs:
        d["_id"] = str(d["_id"])

    docs.sort(key=lambda x: x.get("date", ""), reverse=True)
    return docs


@router.post("/")
def add_group_photo(photo: GroupPhoto):
    photo_data = photo.dict()
    if not photo_data.get("uid"):
        photo_data["uid"] = str(uuid.uuid4())

    gallery_db.update_one({"uid": photo_data["uid"]}, {"$set": photo_data}, upsert=True)
    return photo_data


@router.delete("/")
def delete_group_photo(uid: str = Query(..., description="삭제할 사진의 UID")):
    result = gallery_db.delete_one({"uid": uid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Photo not found")
    return {"message": f"Photo '{uid}' deleted successfully"}
