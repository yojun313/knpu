from fastapi import APIRouter, Depends, HTTPException, Query
from app.db import papers_db, user_logs_db
from app.models import PaperRequest
from app.auth.dependencies import require_admin
from datetime import datetime, timezone
from shared.user_log import insert_log
import uuid
from app.libs.crawl_papers import fetch_bib


router = APIRouter()


@router.get("/")
def list_papers():
    docs = list(papers_db.find())
    for d in docs:
        d.pop("_id", None)

    grouped: dict[int, list[dict]] = {}
    for d in docs:
        grouped.setdefault(d.get("year"), []).append(d)

    result = []
    for year, papers in grouped.items():
        papers.sort(key=lambda p: p.get("fetched_at", ""), reverse=True)
        result.append({"year": year, "papers": papers})

    result.sort(key=lambda x: int(x.get("year") or 0), reverse=True)
    return result


@router.post("/")
def upsert_paper(paper: PaperRequest, admin=Depends(require_admin)):
    paper_data = paper.dict(by_alias=True)

    if not paper_data.get("uid"):
        paper_data["uid"] = str(uuid.uuid4())

    paper_data["fetched_at"] = (
        paper_data.get("fetched_at") or datetime.now(timezone.utc).isoformat()
    )

    papers_db.update_one(
        {"uid": paper_data["uid"]},
        {"$set": paper_data},
        upsert=True,
    )
    insert_log(
        user_logs_db,
        admin["sub"],
        "homepage.paper.upsert",
        "homepage",
        target={
            "type": "paper",
            "id": paper_data["uid"],
            "name": paper_data.get("title"),
        },
    )
    return paper_data


@router.delete("/")
def delete_paper(
    uid: str = Query(..., description="삭제할 논문의 UID"),
    admin=Depends(require_admin),
):
    result = papers_db.delete_one({"uid": uid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Paper not found")
    insert_log(
        user_logs_db,
        admin["sub"],
        "homepage.paper.delete",
        "homepage",
        target={"type": "paper", "id": uid},
    )
    return {"message": f"Paper '{uid}' deleted successfully"}


@router.get("/crawl", dependencies=[Depends(require_admin)])
def crawl_paper(
    title: str = Query(..., description="논문 제목"),
    journal_type: str = Query(..., alias="type", description="SCI / SCOPUS / KCI"),
):
    try:
        record = fetch_bib(title, journal_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if record is None:
        raise HTTPException(status_code=404, detail="메타데이터를 찾을 수 없습니다")

    return record
