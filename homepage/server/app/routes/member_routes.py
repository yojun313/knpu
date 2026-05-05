from typing import List
from fastapi import APIRouter
from app.models import Member
from app.db import members_db

router = APIRouter()

@router.get("/")
def list_members():
    docs = list(members_db.find())
    for d in docs:
        d["_id"] = str(d["_id"])

    # 정렬 기준 정의
    section_order = ["교수", "수석연구위원", "연구위원", "대학원 과정", "연구원", "선임연구원"]
    section_order_map = {s: i for i, s in enumerate(section_order)}

    position_order = ["박사과정", "석사과정", "선임연구원", "연구원"]
    position_order_map = {p: i for i, p in enumerate(position_order)}

    docs.sort(
        key=lambda d: (
            section_order_map.get(d.get("section"), len(section_order_map)),
            position_order_map.get(d.get("position"), len(position_order_map))
        )
    )
    
    return docs
