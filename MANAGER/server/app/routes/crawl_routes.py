from fastapi import APIRouter
from app.models.crawl_model import CrawlDbCreateDto, DataInfo
from app.services.crawl_service import (
    createCrawlDb,
    deleteCrawlDb,
    getCrawlDbList,
    getCrawlDbInfo,
    updateCrawlDb
)

router = APIRouter()

@router.post("/add")
def create_crawl_db(crawlDb: CrawlDbCreateDto):
    return createCrawlDb(crawlDb)

@router.delete("/{uid}")
def delete_crawl_db(uid: str):
    return deleteCrawlDb(uid)

@router.get("/list")
def get_crawl_db_list():
    return getCrawlDbList()

@router.get("/{uid}/info")
def get_crawl_db_info(uid: str):
    return getCrawlDbInfo(uid)

@router.put("/{uid}/datainfo")
def update_crawl_db_datainfo(uid: str, dataInfo: DataInfo):
    return updateCrawlDb(uid, dataInfo)