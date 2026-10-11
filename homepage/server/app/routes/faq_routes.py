import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from app.db import admission_faq_db, admission_faq_categories_db, user_logs_db
from app.auth.dependencies import get_current_user
from app.auth.content import (
    save_content,
    delete_content,
    require_content_owner,
    check_content_update,
)
from app.models import FaqItem, FaqCategory
from system.logging.user_log import insert_log

router = APIRouter()

_BIG = 10**9


def _category_order_map() -> dict:
    return {
        c["name"]: c.get("order", 0)
        for c in admission_faq_categories_db.find({}, {"name": 1, "order": 1})
    }


# ── 카테고리 ─────────────────────────────────────────────────────────


@router.get("/categories")
def list_faq_categories():
    """FAQ 카테고리(그룹) 목록을 order 오름차순으로 반환한다. 공개."""
    docs = list(admission_faq_categories_db.find())
    for d in docs:
        d["_id"] = str(d["_id"])
    docs.sort(key=lambda d: (d.get("order", 0), d.get("name", "")))
    return docs


@router.post("/categories")
def upsert_faq_category(category: FaqCategory, admin=Depends(get_current_user)):
    data = category.dict()
    data["name"] = (data.get("name") or "").strip()
    if not data["name"]:
        raise HTTPException(
            status_code=400, detail="카테고리 이름을 입력해 주시기 바랍니다."
        )

    existing = (
        admission_faq_categories_db.find_one({"uid": data["uid"]})
        if data.get("uid")
        else None
    )

    if existing:
        require_content_owner(existing, admin)
        if admin.get("role") != "admin" and existing["name"] != data["name"]:
            for item in admission_faq_db.find({"category": existing["name"]}):
                require_content_owner(item, admin)

    # 이름 중복 방지 (자기 자신 제외)
    dup = admission_faq_categories_db.find_one({"name": data["name"]})
    if dup and (not existing or dup.get("uid") != existing.get("uid")):
        raise HTTPException(
            status_code=400, detail="이미 같은 이름의 카테고리가 있습니다."
        )

    if not data.get("uid"):
        data["uid"] = str(uuid.uuid4())

    old_name = existing.get("name") if existing else None

    save_content(admission_faq_categories_db, data, admin)

    # 이름이 바뀌면 소속 FAQ 항목의 category 도 함께 갱신한다.
    renamed = 0
    if old_name and old_name != data["name"]:
        rename_query = {"category": old_name}
        if admin.get("role") != "admin":
            rename_query["created_by"] = admin["sub"]
        renamed = admission_faq_db.update_many(
            rename_query, {"$set": {"category": data["name"]}}
        ).modified_count

    result = admission_faq_categories_db.find_one({"uid": data["uid"]})
    result["_id"] = str(result["_id"])
    insert_log(
        user_logs_db,
        admin["sub"],
        "homepage.faq.category.upsert",
        "homepage",
        target={"type": "faq-category", "id": data["uid"], "name": data["name"]},
        metadata={"renamed_items": renamed} if renamed else None,
    )
    return result


@router.delete("/categories")
def delete_faq_category(
    uid: str = Query(..., description="삭제할 카테고리의 UID"),
    admin=Depends(get_current_user),
):
    doc = admission_faq_categories_db.find_one({"uid": uid})
    if not doc:
        raise HTTPException(status_code=404, detail="Category not found")

    require_content_owner(doc, admin)
    in_use = admission_faq_db.count_documents({"category": doc["name"]})
    if in_use:
        raise HTTPException(
            status_code=400,
            detail=f"이 카테고리를 사용하는 FAQ가 {in_use}개 있습니다. 먼저 해당 FAQ의 분류를 바꾸거나 삭제해 주시기 바랍니다.",
        )

    delete_content(admission_faq_categories_db, uid, admin)
    insert_log(
        user_logs_db,
        admin["sub"],
        "homepage.faq.category.delete",
        "homepage",
        target={"type": "faq-category", "id": uid, "name": doc["name"]},
    )
    return {"message": f"Category '{doc['name']}' deleted successfully"}


# ── FAQ 항목 ─────────────────────────────────────────────────────────


@router.get("/")
def list_faq():
    """입시(admission) 페이지의 FAQ 항목 전체를 (카테고리 순서, 항목 순서)로 정렬해 반환한다. 공개."""
    cat_order = _category_order_map()
    docs = list(admission_faq_db.find())
    for d in docs:
        d["_id"] = str(d["_id"])
    docs.sort(
        key=lambda d: (
            cat_order.get(d.get("category", ""), _BIG),
            d.get("order", 0),
            str(d.get("_id")),
        )
    )
    return docs


@router.post("/")
def upsert_faq(item: FaqItem, admin=Depends(get_current_user)):
    data = item.dict()
    data["category"] = (data.get("category") or "").strip()
    if not data.get("uid"):
        data["uid"] = str(uuid.uuid4())

    check_content_update(admission_faq_db, data, admin)

    # 카테고리 관리 UI를 거치지 않고 새 분류가 들어오면 자동으로 등록해 그룹 순서를 부여한다.
    if data["category"] and not admission_faq_categories_db.find_one(
        {"name": data["category"]}
    ):
        max_order = max(
            (c.get("order", 0) for c in admission_faq_categories_db.find()),
            default=0,
        )
        admission_faq_categories_db.insert_one(
            {
                "uid": str(uuid.uuid4()),
                "name": data["category"],
                "order": max_order + 10,
                "created_by": admin["sub"],
            }
        )

    save_content(admission_faq_db, data, admin)

    result = admission_faq_db.find_one({"uid": data["uid"]})
    if not result:
        raise HTTPException(status_code=500, detail="FAQ upsert failed")
    result["_id"] = str(result["_id"])
    insert_log(
        user_logs_db,
        admin["sub"],
        "homepage.faq.upsert",
        "homepage",
        target={"type": "faq", "id": data["uid"], "name": data.get("question")},
    )
    return result


@router.delete("/")
def delete_faq(
    uid: str = Query(..., description="삭제할 FAQ 항목의 UID"),
    admin=Depends(get_current_user),
):
    result = delete_content(admission_faq_db, uid, admin)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="FAQ not found")
    insert_log(
        user_logs_db,
        admin["sub"],
        "homepage.faq.delete",
        "homepage",
        target={"type": "faq", "id": uid},
    )
    return {"message": f"FAQ '{uid}' deleted successfully"}
