from fastapi import APIRouter, Query, Body
from app.models.crawl_model import CrawlDbCreateDto, CrawlLogCreateDto, DataInfo, SaveCrawlDbOption
from app.services.crawl_service import (
    createCrawlDb,
    deleteCrawlDb,
    getCrawlDbList,
    getCrawlDbInfo,
    updateCrawlDb,
    createCrawlLog,
    saveCrawlDb
)
import zipfile
from fastapi.responses import StreamingResponse
import os
import io
import shutil
from starlette.responses import FileResponse

router = APIRouter()

@router.post("/add")
def create_crawl_db(crawlDb: CrawlDbCreateDto):
    return createCrawlDb(crawlDb)

@router.post("/add/log")
def create_crawl_db(crawlLog: CrawlLogCreateDto):
    return createCrawlLog(crawlLog)

@router.delete("/{uid}")
def delete_crawl_db(uid: str):
    return deleteCrawlDb(uid)

@router.get("/list")
def get_crawl_db_list(sort_by: str = Query("starttime", enum=["starttime", "keyword"])):
    return getCrawlDbList(sort_by)

@router.get("/{uid}/info")
def get_crawl_db_info(uid: str):
    return getCrawlDbInfo(uid)

@router.put("/{uid}/datainfo")
def update_crawl_db_datainfo(uid: str, dataInfo: DataInfo):
    return updateCrawlDb(uid, dataInfo)

@router.put("/{uid}/error")
def update_crawl_db_datainfo(uid: str, dataInfo: DataInfo):
    return updateCrawlDb(uid, dataInfo, error=True)

@router.post("/{uid}/save")
def save_crawl_db(uid: str, save_option: SaveCrawlDbOption = Body(...)):
    # 1) CSV 폴더 생성
    folder_path = saveCrawlDb(uid, save_option)

    # 2) ZIP 만들기
    zip_path = shutil.make_archive(folder_path, "zip", root_dir=folder_path)

    # 3) 전송할 파일 이름 (원본 폴더명 + .zip)
    filename = os.path.basename(zip_path)  # 여기에 한글이 섞여 있어도 OK

    # 4) FileResponse에 filename= 으로 넘기기
    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=filename,       # ★ 이렇게만 해 주시면
        # background=…            # (원하시면 삭제 후 백그라운드 작업까지)
    )
