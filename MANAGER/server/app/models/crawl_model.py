from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class DataInfo(BaseModel):
    totalArticleCnt: int
    totalReplyCnt: int
    totalRereplyCnt: int

class CrawlDbListSchema(BaseModel):
    uid: str
    name: str
    crawlOption: int
    startTime: datetime
    endTime: Optional[datetime]
    requester: str
    keyword: str
    dbSize: float
    crawlCom: str
    crawlSpeed: int
    dataInfo: DataInfo

class CrawlDbCreateDto(BaseModel):
    name: str
    crawlOption: int
    requester: str
    keyword: str
    dbSize: float
    crawlCom: str
    crawlSpeed: int