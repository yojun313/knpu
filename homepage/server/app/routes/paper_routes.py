from fastapi import APIRouter, HTTPException
from app.db import papers_db

router = APIRouter()

@router.get("/")
def list_papers():
    docs = list(papers_db.find())
    for d in docs:
        d.pop("_id", None)

        # 내부 papers 리스트를 datetime 기준으로 내림차순 정렬
        d["papers"] = sorted(
            d.get("papers", []),
            key=lambda p: p.get("datetime", ""),  # 문자열이지만 ISO 형식이라 정렬 가능
            reverse=True
        )

    # 연도 기준 내림차순 정렬
    docs.sort(key=lambda x: int(x.get("year", 0)), reverse=True)

    return docs

