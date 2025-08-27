from fastapi import APIRouter, Query, Body, Depends
from app.models.crawl_model import CrawlDbCreateDto, CrawlLogCreateDto, DataInfo, SaveCrawlDbOption
from app.services.crawl_service import (
    createCrawlDb,
    deleteCrawlDb,
    getCrawlDbList,
    getCrawlDbInfo,
    updateCrawlDb,
    createCrawlLog,
    saveCrawlDb,
    previewCrawlDb
)
from app.services.user_service import log_user
from app.libs.jwt import verify_token

router = APIRouter()

@router.post("/add")
def create_crawl_db(crawlDb: CrawlDbCreateDto):
    return createCrawlDb(crawlDb)


@router.post("/add/log")
def create_crawl_db(crawlLog: CrawlLogCreateDto):
    return createCrawlLog(crawlLog)


@router.delete("/{uid}",)
def delete_crawl_db(uid: str, userUid = Depends(verify_token)):
    log_user(userUid, f"Requested to delete crawl DB: {uid}")
    return deleteCrawlDb(uid)

@router.get("/list")
def get_crawl_db_list(sort_by: str = Query("starttime", enum=["starttime", "keyword"]), 
                      mine: int = Query("mine", enum=[0, 1]),
                      userUid = Depends(verify_token)):
    return getCrawlDbList(sort_by, mine, userUid)


@router.get("/{uid}/info")
def get_crawl_db_info(uid: str):
    return getCrawlDbInfo(uid)


@router.put("/{uid}/datainfo")
def update_crawl_db_datainfo(uid: str, dataInfo: DataInfo):
    return updateCrawlDb(uid, dataInfo)


@router.get("/{uid}/preview")
def get_crawl_db_info(uid: str, userUid = Depends(verify_token)):
    log_user(userUid, f"Requested preview for crawl DB: {uid}")
    return previewCrawlDb(uid)


@router.put("/{uid}/error")
def update_crawl_db_datainfo_error(uid: str, dataInfo: DataInfo):
    return updateCrawlDb(uid, dataInfo, error=True)


@router.post("/{uid}/save")
def save_crawl_db(uid: str, save_option: SaveCrawlDbOption = Body(...), userUid = Depends(verify_token)):
    log_user(userUid, f"Requested to save crawl DB: {uid}")
    return saveCrawlDb(uid, save_option)
