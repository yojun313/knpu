from fastapi import APIRouter, HTTPException, Query
from app.db import papers_db
from app.models import PaperRequest
from datetime import datetime, timezone
import uuid

router = APIRouter()


@router.get("/")
def list_papers():
    docs = list(papers_db.find())
    for d in docs:
        d.pop("_id", None)

        d["papers"] = sorted(
            d.get("papers", []),
            key=lambda p: p.get("datetime", ""),
            reverse=True,
        )

    docs.sort(key=lambda x: int(x.get("year", 0)), reverse=True)

    return docs


@router.post("/")
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


@router.delete("/")
def delete_paper(uid: str = Query(..., description="삭제할 논문의 UID")):
    all_docs = papers_db.find({})
    for doc in all_docs:
        papers = doc.get("papers", [])
        new_papers = [p for p in papers if p.get("uid") != uid]
        if len(new_papers) != len(papers):
            papers_db.update_one({"_id": doc["_id"]}, {"$set": {"papers": new_papers}})
            return {"message": f"Paper '{uid}' deleted successfully"}

    raise HTTPException(status_code=404, detail="Paper not found")
