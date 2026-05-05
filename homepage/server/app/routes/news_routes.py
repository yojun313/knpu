from fastapi import APIRouter
from app.db import news_db
from datetime import datetime
from app.models import News 

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
