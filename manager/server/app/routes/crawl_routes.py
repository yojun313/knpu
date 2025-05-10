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
from fastapi.responses import StreamingResponse
import os
import shutil
from starlette.responses import FileResponse
from starlette.background import BackgroundTask
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
                      userUid = Depends(verify_token)):
    return getCrawlDbList(sort_by)


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
def update_crawl_db_datainfo(uid: str, dataInfo: DataInfo):
    return updateCrawlDb(uid, dataInfo, error=True)


@router.post("/{uid}/save")
def save_crawl_db(uid: str, save_option: SaveCrawlDbOption = Body(...), userUid = Depends(verify_token)):
    log_user(userUid, f"Requested to save crawl DB: {uid}")
    # 1) CSV 폴더 생성
    folder_path = saveCrawlDb(uid, save_option)

    # 2) ZIP 만들기
    zip_path = shutil.make_archive(folder_path, "zip", root_dir=folder_path)

    # 3) 전송할 파일 이름 (원본 폴더명 + .zip)
    filename = os.path.basename(zip_path)  # 여기에 한글이 섞여 있어도 OK

    background_task = BackgroundTask(
        cleanup_folder_and_zip, folder_path, zip_path)
    # 4) FileResponse에 filename= 으로 넘기기
    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=filename,
        background=background_task,
    )


def cleanup_folder_and_zip(folder_path: str, zip_path: str):
    # 폴더와 ZIP 파일을 삭제
    shutil.rmtree(folder_path, ignore_errors=True)
    try:
        os.remove(zip_path)
    except OSError:
        pass
