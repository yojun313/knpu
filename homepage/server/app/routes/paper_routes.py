from fastapi import APIRouter, Depends, HTTPException, Query
from app.db import papers_db, user_logs_db
from app.models import PaperRequest
from app.auth.dependencies import require_admin
from datetime import datetime, timezone
from system.logging.user_log import insert_log
import re
import uuid
from app.libs.crawl_papers import fetch_bib


router = APIRouter()


def _norm_doi(value: str | None) -> str:
    """DOI 정규화 — 프로토콜/도메인 접두사 제거, 소문자."""
    d = (value or "").strip().lower()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
    return d


def _norm_title(value: str | None) -> str:
    """제목 정규화 — 소문자화, 구두점 제거, 공백 축약."""
    t = (value or "").lower()
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _find_duplicate(paper_data: dict, exclude_uid: str | None) -> dict | None:
    """이미 등록된 논문과 겹치는지 검사한다.
    - DOI가 있으면 DOI 일치(연도 무관)를 우선한다.
    - 없으면 정규화한 제목 + 연도가 모두 같은 경우를 중복으로 본다.
    편집(같은 uid)일 때는 자기 자신을 제외한다.
    """
    doi = _norm_doi(paper_data.get("doi"))
    norm_title = _norm_title(paper_data.get("title"))
    year = paper_data.get("year")

    for existing in papers_db.find(
        {}, {"uid": 1, "title": 1, "doi": 1, "year": 1, "_id": 0}
    ):
        if exclude_uid and existing.get("uid") == exclude_uid:
            continue
        if doi and _norm_doi(existing.get("doi")) == doi:
            return existing
        if (
            norm_title
            and _norm_title(existing.get("title")) == norm_title
            and existing.get("year") == year
        ):
            return existing
    return None


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

    incoming_uid = paper_data.get("uid") or None

    duplicate = _find_duplicate(paper_data, exclude_uid=incoming_uid)
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=(
                f"이미 등록된 논문입니다: '{duplicate.get('title')}'"
                f" ({duplicate.get('year')})"
            ),
        )

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
