"""매니저 데스크톱 앱이 직접 호출하는 크롤링 DB 조회/다운로드 API.

예전엔 매니저 데스크톱 앱 -> manager.knpu.re.kr/api/crawls/* -> (crawler는 자기 웹
대시보드에서 같은 데이터를 다시 manager.knpu.re.kr로 HTTP 프록시) 구조였다. 이제
kemkim/network/statistics와 동일하게 앱이 crawler.knpu.re.kr을 직접 호출한다."""

from fastapi import APIRouter, Query, Body, Depends
from app.routes.dependencies import get_current_user
from app.models.job_model import CrawlSaveOption
from app.services.crawls_service import (
    deleteCrawlDb,
    stopCrawlDb,
    getCrawlDbList,
    getCrawlDbInfo,
    getCrawlLog,
    previewCrawlDb,
    saveCrawlDb,
)

router = APIRouter()


@router.get("/{uid}/log")
def get_crawl_db_log(uid: str):
    return getCrawlLog(uid)


@router.delete("/{uid}")
def delete_crawl_db(uid: str, user=Depends(get_current_user)):
    return deleteCrawlDb(uid, user["uid"])


@router.put("/{uid}/stop")
def stop_crawl_db(uid: str, user=Depends(get_current_user)):
    return stopCrawlDb(uid, user["uid"])


@router.get("/list")
def get_crawl_db_list(
    sort_by: str = Query("starttime", enum=["starttime", "keyword"]),
    mine: int = Query("mine", enum=[0, 1]),
    user=Depends(get_current_user),
):
    return getCrawlDbList(sort_by, mine, user)


@router.get("/{uid}/info")
def get_crawl_db_info(uid: str, user=Depends(get_current_user)):
    return getCrawlDbInfo(uid, user["uid"])


@router.get("/{uid}/preview")
def get_crawl_db_preview(uid: str, user=Depends(get_current_user)):
    return previewCrawlDb(uid, user["uid"])


@router.post("/{uid}/save")
def save_crawl_db(
    uid: str, save_option: CrawlSaveOption = Body(...), user=Depends(get_current_user)
):
    return saveCrawlDb(uid, save_option.model_dump(), user["uid"], user["name"])
