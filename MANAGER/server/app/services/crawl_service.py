from app.db import crawlDbList_collection
from app.libs.exceptions import ConflictException, NotFoundException 
from app.models.crawl_model import CrawlDbCreateDto, DataInfo
from app.utils.mongo import clean_doc
from fastapi.responses import JSONResponse
from collections import OrderedDict
from datetime import datetime, timezone
import uuid

def createCrawlDb(crawlDb: CrawlDbCreateDto):
    crawlDb_dict = crawlDb.model_dump()
    
    existing_crawlDb = crawlDbList_collection.find_one({"name": crawlDb_dict["name"]})
    if existing_crawlDb:
        raise ConflictException("CrawlDB with this name already exists")
    
    ordered_dict = OrderedDict([("uid", str(uuid.uuid4()))])
    ordered_dict.update(crawlDb_dict)
    ordered_dict['dataInfo'] = {
        "totalArticleCnt": 0,
        "totalReplyCnt": 0,
        "totalRereplyCnt": 0
    }
    
    ordered_dict['startTime'] = datetime.now(timezone.utc)
    ordered_dict['endTime'] = None
    
    crawlDbList_collection.insert_one(ordered_dict)
    
    return JSONResponse(
        status_code=201,
        content={"message": "CrawlDB created", "data": clean_doc(crawlDb_dict)},
    )
    
def deleteCrawlDb(uid: str):
    result = crawlDbList_collection.delete_one({"uid": uid})
    
    if result.deleted_count == 0:
        raise NotFoundException("CrawlDB not found")
    
    return JSONResponse(
        status_code=200,
        content={"message": "CrawlDB deleted"},
    )
    
def getCrawlDbList():
    crawlDbList = crawlDbList_collection.find()
    
    if not crawlDbList:
        raise NotFoundException("No CrawlDBs found")
    
    crawlDbList = [clean_doc(crawlDb) for crawlDb in crawlDbList]
    
    return JSONResponse(
        status_code=200,
        content={"message": "CrawlDB list retrieved", "data": crawlDbList},
    )

def getCrawlDbInfo(uid: str):
    crawlDb = crawlDbList_collection.find_one({"uid": uid})
    
    if not crawlDb:
        raise NotFoundException("CrawlDB not found")
    
    return JSONResponse(
        status_code=200,
        content={"message": "CrawlDB retrieved", "data": clean_doc(crawlDb)},
    )   
    
def updateCrawlDb(uid: str, dataInfo: DataInfo):

    data_info_dict = dataInfo.model_dump()

    result = crawlDbList_collection.update_one(
        {"uid": uid},
        {"$set": {"dataInfo": data_info_dict, "endTime": datetime.now(timezone.utc)}}
    )

    if result.matched_count == 0:
        raise NotFoundException("CrawlDB not found")

    updated = crawlDbList_collection.find_one({"uid": uid})

    return JSONResponse(
        status_code=200,
        content={
            "message": "CrawlDB updated",
            "data": clean_doc(updated)
        },
    )
    
