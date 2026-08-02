import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from app.db import popup_db, user_logs_db
from app.auth.dependencies import require_admin
from datetime import datetime
from app.models import Popup
from shared.user_log import insert_log

router = APIRouter()


@router.get("/")
def list_popups():
    docs = list(popup_db.find())
    for d in docs:
        d["_id"] = str(d["_id"])
    docs.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return docs


@router.post("/")
def upsert_popup(popup: Popup, admin=Depends(require_admin)):
    data = popup.dict()
    if not data.get("uid"):
        data["uid"] = str(uuid.uuid4())
    if not data.get("created_at"):
        data["created_at"] = datetime.utcnow().isoformat()

    popup_db.update_one({"uid": data["uid"]}, {"$set": data}, upsert=True)

    result = popup_db.find_one({"uid": data["uid"]})
    if not result:
        raise HTTPException(status_code=500, detail="Popup upsert failed")
    result["_id"] = str(result["_id"])
    insert_log(
        user_logs_db,
        admin["sub"],
        "homepage.popup.upsert",
        "homepage",
        target={"type": "popup", "id": data["uid"]},
    )
    return result


@router.delete("/")
def delete_popup(
    uid: str = Query(..., description="삭제할 팝업의 UID"),
    admin=Depends(require_admin),
):
    result = popup_db.delete_one({"uid": uid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Popup not found")
    insert_log(
        user_logs_db,
        admin["sub"],
        "homepage.popup.delete",
        "homepage",
        target={"type": "popup", "id": uid},
    )
    return {"message": f"Popup '{uid}' deleted successfully"}
