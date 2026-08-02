from fastapi import APIRouter, Depends, Query, HTTPException
from app.db import news_db, user_logs_db
from app.auth.dependencies import require_admin
from datetime import datetime
from app.models import News
from shared.user_log import insert_log
import uuid


router = APIRouter()


@router.get("/")
def list_news():
    docs = list(news_db.find())
    for d in docs:
        d["_id"] = str(d["_id"])

    # "YYYY.MM" 형태의 date를 datetime 객체로 변환하여 정렬
    def parse_date(doc):
        try:
            return datetime.strptime(doc.get("date", "1900.01"), "%Y.%m")
        except ValueError:
            # 잘못된 형식일 경우 오래된 날짜 반환
            return datetime(1900, 1, 1)

    docs.sort(key=parse_date, reverse=True)  # 최신순 정렬
    return docs


@router.post("/")
def upsert_news(news: News, admin=Depends(require_admin)):
    news_data = news.dict(by_alias=True)
    if "uid" not in news_data or not news_data["uid"]:
        news_data["uid"] = str(uuid.uuid4())

    result = news_db.update_one(
        {"uid": news_data["uid"]}, {"$set": news_data}, upsert=True
    )

    new_news = news_db.find_one({"uid": news_data["uid"]})
    if not new_news:
        raise HTTPException(status_code=500, detail="News upsert failed")

    new_news["_id"] = str(new_news["_id"])
    insert_log(
        user_logs_db,
        admin["sub"],
        "homepage.news.upsert",
        "homepage",
        target={"type": "news", "id": news_data["uid"], "name": news_data.get("title")},
    )
    return new_news


@router.delete("/")
def delete_news(
    uid: str = Query(..., description="삭제할 뉴스의 UID"),
    admin=Depends(require_admin),
):
    result = news_db.delete_one({"uid": uid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="News not found")
    insert_log(
        user_logs_db,
        admin["sub"],
        "homepage.news.delete",
        "homepage",
        target={"type": "news", "id": uid},
    )
    return {"message": f"News '{uid}' deleted successfully"}
