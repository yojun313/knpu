from fastapi import APIRouter, Depends, Query, UploadFile, File
from app.models import Member
from app.db import members_db, user_logs_db
from app.auth.dependencies import require_admin, get_current_user
from app.auth import service as auth_service
from app.libs import r2
from shared.user_log import insert_log
from fastapi import HTTPException
import uuid

router = APIRouter()


@router.get("/me")
def my_linked_member(user=Depends(get_current_user)):
    return auth_service.get_linked_member(user["sub"])


@router.post("/me/photo")
async def upload_my_member_photo(
    file: UploadFile = File(...), user=Depends(get_current_user)
):
    url = r2.upload_fileobj(file, "members")
    return auth_service.update_my_member_photo(user["sub"], url)


@router.get("/")
def list_members():
    docs = list(members_db.find())
    for d in docs:
        d["_id"] = str(d["_id"])

    # 정렬 기준 정의
    section_order = [
        "교수",
        "수석연구위원",
        "연구위원",
        "대학원 과정",
        "연구원",
        "선임연구원",
    ]
    section_order_map = {s: i for i, s in enumerate(section_order)}

    position_order = ["박사과정", "석사과정", "선임연구원", "연구원"]
    position_order_map = {p: i for i, p in enumerate(position_order)}

    docs.sort(
        key=lambda d: (
            section_order_map.get(d.get("section"), len(section_order_map)),
            position_order_map.get(d.get("position"), len(position_order_map)),
        )
    )

    return docs


@router.post("/")
def upsert_member(member: Member, admin=Depends(require_admin)):
    member_data = member.dict(by_alias=True)
    if "uid" not in member_data or not member_data["uid"]:
        member_data["uid"] = str(uuid.uuid4())

    result = members_db.update_one(
        {"uid": member_data["uid"]}, {"$set": member_data}, upsert=True
    )

    new_member = members_db.find_one({"uid": member_data["uid"]})
    if not new_member:
        raise HTTPException(status_code=500, detail="Member upsert failed")

    new_member["_id"] = str(new_member["_id"])
    insert_log(
        user_logs_db,
        admin["sub"],
        "homepage.member.upsert",
        "homepage",
        target={
            "type": "member",
            "id": member_data["uid"],
            "name": member_data.get("name"),
        },
    )
    return new_member


@router.get("/options")
def get_member_options():
    return {
        "positions": [
            "교수",
            "연구위원",
            "수석연구위원",
            "박사과정",
            "석사과정",
            "박사졸업",
            "석사졸업",
            "연구원",
        ],
        "sections": ["교수", "연구위원", "대학원 과정", "연구원", "Alumni"],
    }


@router.delete("/")
def delete_member(
    uid: str = Query(..., description="삭제할 멤버의 UID"),
    admin=Depends(require_admin),
):
    doc = members_db.find_one({"uid": uid})
    result = members_db.delete_one({"uid": uid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Member not found")
    insert_log(
        user_logs_db,
        admin["sub"],
        "homepage.member.delete",
        "homepage",
        target={"type": "member", "id": uid, "name": (doc or {}).get("name")},
    )
    return {"message": f"Member '{uid}' deleted successfully"}
