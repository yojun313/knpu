from app.db import crawlList_db, mysql_db, crawlLog_db
from app.libs.exceptions import ConflictException, NotFoundException 
from app.models.crawl_model import CrawlDbCreateDto, DataInfo, CrawlLogCreateDto
from app.utils.mongo import clean_doc
from fastapi.responses import JSONResponse
from collections import OrderedDict
from datetime import datetime, timezone, timedelta
import uuid

def createCrawlDb(crawlDb: CrawlDbCreateDto):
    crawlDb_dict = crawlDb.model_dump()
    
    existing_crawlDb = crawlList_db.find_one({"name": crawlDb_dict["name"]})
    if existing_crawlDb:
        raise ConflictException("CrawlDB with this name already exists")
    
    ordered_dict = OrderedDict([("uid", str(uuid.uuid4()))])
    ordered_dict.update(crawlDb_dict)
    ordered_dict['dataInfo'] = {
        "totalArticleCnt": 0,
        "totalReplyCnt": 0,
        "totalRereplyCnt": 0
    }
    now_kst = datetime.now(timezone.utc).astimezone(
        timezone(timedelta(hours=9))
    ).strftime('%Y-%m-%d %H:%M')
    
    ordered_dict['startTime'] = now_kst
    ordered_dict['endTime'] = None
    
    crawlList_db.insert_one(ordered_dict)
    
    return JSONResponse(
        status_code=201,
        content={"message": "CrawlDB created", "data": clean_doc(ordered_dict)},
    )

def createCrawlLog(crawlLog: CrawlLogCreateDto):
    crawlLog_dict = crawlLog.model_dump()
    
    existing_crawlLog = crawlList_db.find_one({"uid": crawlLog_dict["uid"]})
    if existing_crawlLog:
        raise ConflictException("CrawlLog with this uid already exists")
    
    dict = {
        'uid': crawlLog_dict['uid'],
        'content': crawlLog_dict['content'],
    }
    
    crawlLog_db.insert_one(dict)
    
    return JSONResponse(
        status_code=201,
        content={"message": "CrawlLog created", "data": clean_doc(crawlLog_dict)},
    )   
    
    
def deleteCrawlDb(uid: str):
    result = crawlList_db.delete_one({"uid": uid})
    
    if result.deleted_count == 0:
        raise NotFoundException("CrawlDB not found")
    
    return JSONResponse(
        status_code=200,
        content={"message": "CrawlDB deleted"},
    )
    
def getCrawlDbList():
    crawlDbList = crawlList_db.find()
    
    if not crawlDbList:
        raise NotFoundException("No CrawlDBs found")
    
    crawlDbList = [clean_doc(crawlDb) for crawlDb in crawlDbList]
    
    return JSONResponse(
        status_code=200,
        content={"message": "CrawlDB list retrieved", "data": crawlDbList},
    )

def getCrawlDbInfo(uid: str):
    crawlDb = crawlList_db.find_one({"uid": uid})
    
    if not crawlDb:
        raise NotFoundException("CrawlDB not found")
    
    return JSONResponse(
        status_code=200,
        content={"message": "CrawlDB retrieved", "data": clean_doc(crawlDb)},
    )   
    
def updateCrawlDb(uid: str, dataInfo, error:bool = False):
    crawlDb = crawlList_db.find_one({"uid": uid})
    if not crawlDb:
        raise NotFoundException("CrawlDB not found")
    
    dbsize = mysql_db.showDBSize(crawlDb['name'])[0]
    data_info_dict = dataInfo.model_dump()
    
    if error:
        result = crawlList_db.update_one(
            {"uid": uid},
            {"$set": {"dataInfo": data_info_dict, "endTime": 'X', "dbSize": dbsize}},
        )

    now_kst = datetime.now(timezone.utc).astimezone(
        timezone(timedelta(hours=9))
    ).strftime('%Y-%m-%d %H:%M')

    result = crawlList_db.update_one(
        {"uid": uid},
        {"$set": {"dataInfo": data_info_dict, "endTime": now_kst, "dbSize": dbsize}},
    )

    if result.matched_count == 0:
        raise NotFoundException("CrawlDB not found")

    return JSONResponse(
        status_code=200,
        content={
            "message": "CrawlDB updated",
        },
    )
    
