from fastapi import APIRouter, HTTPException, Query
from app.models import Member, News, Paper, PaperRequest
from app.db import members_db, news_db, papers_db
import uuid
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import List, Optional

class Member(BaseModel):
    uid: Optional[str] = None
    name: str
    position: str
    affiliation: str
    section: str
    email: str
    학력: List[str] = []
    경력: List[str] = []
    연구: List[str] = []
    image: Optional[str] = ""

router = APIRouter()

@router.post("/member")
def upsert_member(member: Member):
    member_data = member.dict(by_alias=True)
    if "uid" not in member_data or not member_data["uid"]:
        member_data["uid"] = str(uuid.uuid4())

    result = members_db.update_one(
        {"uid": member_data["uid"]},
        {"$set": member_data},
        upsert=True
    )

    new_member = members_db.find_one({"uid": member_data["uid"]})
    if not new_member:
        raise HTTPException(status_code=500, detail="Member upsert failed")

    new_member["_id"] = str(new_member["_id"])
    return new_member

@router.get("/member/options")
def get_member_options():
    return {
        "positions": ["교수", "연구위원", "수석연구위원", "박사과정", "석사과정", "박사졸업", "석사졸업", "연구원"],
        "sections": ["교수", "연구위원", "대학원 과정", "연구원", "Alumni"]
    }
    
@router.post("/news")
def upsert_news(news: News):
    news_data = news.dict(by_alias=True)
    if "uid" not in news_data or not news_data["uid"]:
        news_data["uid"] = str(uuid.uuid4())

    result = news_db.update_one(
        {"uid": news_data["uid"]},
        {"$set": news_data},
        upsert=True
    )

    new_news = news_db.find_one({"uid": news_data["uid"]})
    if not new_news:
        raise HTTPException(status_code=500, detail="News upsert failed")

    new_news["_id"] = str(new_news["_id"])
    return new_news

@router.post("/paper")
def upsert_paper(request: PaperRequest):
    year_str = str(request.year)
    paper_data = request.paper.dict(by_alias=True)
    if "uid" not in paper_data or not paper_data["uid"]:
        paper_data["uid"] = str(uuid.uuid4())    
    else:
        pass
    
    paper_data["datetime"] = datetime.now(timezone.utc).isoformat()
    existing_doc = papers_db.find_one({"year": year_str})

    if not existing_doc:
        papers_db.insert_one({"year": year_str, "papers": [paper_data]})
        return paper_data

    papers_for_year = existing_doc.get("papers", [])
    updated = False
    for i, p in enumerate(papers_for_year):
        if p.get("uid") == paper_data["uid"]:
            papers_for_year[i] = paper_data
            updated = True
            break

    if not updated:
        papers_for_year.append(paper_data)

    papers_db.update_one(
        {"year": year_str},
        {"$set": {"papers": papers_for_year}},
    )

    return paper_data

@router.delete("/member")
def delete_member(uid: str = Query(..., description="삭제할 멤버의 UID")):
    result = members_db.delete_one({"uid": uid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"message": f"Member '{uid}' deleted successfully"}

@router.delete("/news")
def delete_news(uid: str = Query(..., description="삭제할 뉴스의 UID")):
    result = news_db.delete_one({"uid": uid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="News not found")
    return {"message": f"News '{uid}' deleted successfully"}

@router.delete("/paper")
def delete_paper(uid: str = Query(..., description="삭제할 논문의 UID")):
    all_docs = papers_db.find({})
    for doc in all_docs:
        papers = doc.get("papers", [])
        new_papers = [p for p in papers if p.get("uid") != uid]
        if len(new_papers) != len(papers):
            papers_db.update_one(
                {"_id": doc["_id"]},
                {"$set": {"papers": new_papers}}
            )
            return {"message": f"Paper '{uid}' deleted successfully"}

    raise HTTPException(status_code=404, detail="Paper not found")
