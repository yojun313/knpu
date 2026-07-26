from fastapi import APIRouter, Depends, Query, UploadFile, File
from app.models import Member
from app.db import members_db
from app.auth.dependencies import require_admin, get_current_user
from app.auth import service as auth_service
from app.libs import r2
from fastapi import HTTPException
import uuid

router = APIRouter()


@router.get("/me")
def my_linked_member(user=Depends(get_current_user)):
    """로그인한 사용자와 이름이 일치하는 홈페이지 멤버 프로필(있으면)을 반환한다.
    마이페이지가 프로필 사진 편집 UI를 보여줄지 판단하는 데 쓴다."""
    return auth_service.get_linked_member(user["sub"])


@router.post("/me/photo")
async def upload_my_member_photo(
    file: UploadFile = File(...), user=Depends(get_current_user)
):
    """일반 사용자가(관리자 아니어도) 자신과 연결된 멤버 프로필의 사진만 바꿀 수 있게 하는
    셀프서비스 엔드포인트. 다른 필드는 손댈 수 없다."""
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


@router.post("/", dependencies=[Depends(require_admin)])
def upsert_member(member: Member):
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


@router.delete("/", dependencies=[Depends(require_admin)])
def delete_member(uid: str = Query(..., description="삭제할 멤버의 UID")):
    result = members_db.delete_one({"uid": uid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"message": f"Member '{uid}' deleted successfully"}
