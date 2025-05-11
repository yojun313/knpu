from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from typing import List

class DataInfo(BaseModel):
    totalArticleCnt: int
    totalReplyCnt: int
    totalRereplyCnt: int

class CrawlDbListSchema(BaseModel):
    uid: str
    name: str
    crawlOption: int
    startTime: str
    endTime: Optional[str]
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
    
class CrawlLogCreateDto(BaseModel):
    uid: str
    content: str
    
class SaveCrawlDbOption(BaseModel):
    pid: str
    dateOption: str
    start_date: str
    end_date: str
    filterOption: bool
    incl_words: List[str]
    excl_words: List[str]
    include_all: bool
    filename_edit: bool
    