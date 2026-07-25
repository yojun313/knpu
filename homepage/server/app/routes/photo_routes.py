from fastapi import APIRouter, Depends, HTTPException, Query
from app.models import GalleryPost
from app.db import gallery_db
from app.auth.dependencies import require_admin
from app.libs import r2
import uuid

router = APIRouter()


@router.get("/")
def list_gallery_posts():
    docs = list(gallery_db.find())
    for d in docs:
        d["_id"] = str(d["_id"])

    docs.sort(key=lambda x: x.get("date", ""), reverse=True)
    return docs


@router.post("/", dependencies=[Depends(require_admin)])
def upsert_gallery_post(post: GalleryPost):
    if not post.photos:
        raise HTTPException(
            status_code=400, detail="사진을 최소 1장 이상 등록해야 합니다."
        )

    post_data = post.dict()
    if not post_data.get("uid"):
        post_data["uid"] = str(uuid.uuid4())

    gallery_db.update_one({"uid": post_data["uid"]}, {"$set": post_data}, upsert=True)
    return post_data


@router.delete("/", dependencies=[Depends(require_admin)])
def delete_gallery_post(uid: str = Query(..., description="삭제할 게시글의 UID")):
    doc = gallery_db.find_one({"uid": uid})
    if not doc:
        raise HTTPException(status_code=404, detail="Post not found")

    for url in doc.get("photos", []):
        try:
            r2.s3.delete_object(Bucket=r2.BUCKET_NAME, Key=r2.object_name_from_url(url))
        except Exception as e:
            print(f"R2 delete failed for {url}: {e}")

    gallery_db.delete_one({"uid": uid})
    return {"message": f"Post '{uid}' and its photos deleted successfully"}
