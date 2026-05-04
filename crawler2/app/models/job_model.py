from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


class JobSubmitRequest(BaseModel):
    name: str                       # 요청자
    crawl_object: int               # 1=NaverNews, 2=Blog, 3=Cafe, 4=YouTube, 5=ChinaDaily, 6=ChinaSina
    start_day: str                  # "20250101"
    end_day: str                    # "20251231"
    option_select: int              # 1,2,3,4
    keyword: str
    priority: int = 0               # 높을수록 먼저 실행


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
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    crawler_status: Optional[dict] = None   # crawler.reportStatus() 결과
    error_message: Optional[str] = None


class QueueConfigUpdate(BaseModel):
    max_concurrent: int = Field(ge=1, le=10)
