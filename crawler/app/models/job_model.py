from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import datetime


class JobSubmitRequest(BaseModel):
    name: str  # 요청자
    crawl_object: (
        int  # 1=NaverNews, 2=Blog, 3=Cafe, 4=YouTube, 5=ChinaDaily, 6=ChinaSina
    )
    start_day: str  # "20250101"
    end_day: str  # "20251231"
    option_select: int  # 1,2,3,4
    keyword: str
    priority: int = 0  # 높을수록 먼저 실행
    speed: int = Field(default=3, ge=1, le=10)  # 비동기 수집 동시 요청 수 (1~10)


class JobStatus(BaseModel):
    job_id: str
    state: Literal["queued", "running", "completed", "stopped", "error"]
    name: str
    crawl_object: int
    start_day: str
    end_day: str
    option_select: int
    keyword: str
    priority: int = 0
    speed: int = 3
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    crawler_status: Optional[dict] = None  # crawler.reportStatus() 결과
    error_message: Optional[str] = None


class QueueConfigUpdate(BaseModel):
    max_concurrent: int = Field(ge=1, le=10)


class ResumeRequest(BaseModel):
    end_date: Optional[str] = None  # "20250101" 형식. 완료된 작업은 필수(확장할 종료일)


class RecrawlRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class CrawlSaveOption(BaseModel):
    pid: str
    dateOption: str  # "all" | "part"
    start_date: str = ""
    end_date: str = ""
    filterOption: bool = False
    incl_words: List[str] = []
    excl_words: List[str] = []
    include_all: bool = False
    filename_edit: bool = False
    encoding: str = "utf-8-sig"  # "utf-8-sig" | "cp949"
    include_token_data: bool = True
    include_manifest: bool = True
