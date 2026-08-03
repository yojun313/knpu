from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from typing import Dict, Optional, Callable
from datetime import datetime
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class CrawlerEntry:
    job_id: str
    crawler: object  # NaverNewsCrawler 등
    meta: dict  # JobSubmitRequest.dict()
    state: str = "running"  # running → completed / stopped / error
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
    future: Optional[Future] = None


class CrawlerRegistry:
    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)
        self.lock = threading.Lock()
        self.active_jobs: Dict[str, CrawlerEntry] = {}
        self.on_job_finished: Optional[Callable[[str], None]] = None

    def submit(self, job_id: str, crawler, meta: dict):
        entry = CrawlerEntry(job_id=job_id, crawler=crawler, meta=meta)
        with self.lock:
            self.active_jobs[job_id] = entry

        future = self.executor.submit(self._run_crawler, job_id, crawler)
        entry.future = future

    def _run_crawler(self, job_id: str, crawler):
        try:
            crawler.main()
            # 중단 요청으로 빠져나온 경우 main()도 정상 반환하므로, running 플래그로
            # 완료와 중단을 구분한다 (그러지 않으면 중단 작업이 완료로 기록된다).
            stopped = hasattr(crawler, "running") and not crawler.running
            self._mark_done(job_id, "stopped" if stopped else "completed")
        except Exception as e:
            logger.exception(f"Crawler {job_id} failed")
            self._mark_done(job_id, "error", str(e))
            # crawler.main()이 예외로 종료 → stopOperator가 호출되지 않았을 수 있음
            if hasattr(crawler, "DBuid") and crawler.DBuid:
                try:
                    from common.storage import errorCrawl, appendCrawlLog

                    appendCrawlLog(crawler.DBuid, "error", f"크롤러 비정상 종료: {e}")
                    errorCrawl(crawler.DBuid)
                except Exception:
                    logger.warning(f"DB 에러 상태 업데이트 실패: {job_id}")

                try:
                    from db import user_logs_db
                    from system.logging.user_log import insert_log

                    insert_log(
                        user_logs_db,
                        getattr(crawler, "requesterUid", None),
                        "crawler.crawl.error",
                        "crawler",
                        message=f"크롤링 비정상 종료: {getattr(crawler, 'DBname', job_id)}",
                        target={
                            "type": "crawl_db",
                            "id": crawler.DBuid,
                            "name": getattr(crawler, "DBname", None),
                        },
                        outcome="failure",
                        metadata={"error": str(e)},
                    )
                except Exception:
                    logger.warning(f"에러 로그 기록 실패: {job_id}")

    def _mark_done(self, job_id: str, state: str, error: str = None):
        with self.lock:
            entry = self.active_jobs.get(job_id)
            if entry:
                entry.state = state
                entry.finished_at = datetime.now()
                entry.error_message = error

        # 콜백은 lock 밖에서 호출 (deadlock 방지)
        if self.on_job_finished:
            try:
                self.on_job_finished(job_id)
            except Exception:
                logger.exception(f"on_job_finished callback failed for {job_id}")

    def get_status(self, job_id: str) -> Optional[dict]:
        with self.lock:
            entry = self.active_jobs.get(job_id)
        if (
            entry
            and entry.state == "running"
            and hasattr(entry.crawler, "reportStatus")
        ):
            return entry.crawler.reportStatus()
        return None

    def get_entry(self, job_id: str) -> Optional[CrawlerEntry]:
        with self.lock:
            return self.active_jobs.get(job_id)

    def stop(self, job_id: str) -> bool:
        with self.lock:
            entry = self.active_jobs.get(job_id)
        if entry and entry.state == "running" and hasattr(entry.crawler, "running"):
            entry.crawler.running = False
            return True
        return False

    def active_count(self) -> int:
        with self.lock:
            return sum(1 for e in self.active_jobs.values() if e.state == "running")

    def all_entries(self) -> list:
        with self.lock:
            return list(self.active_jobs.values())

    def remove_finished(self, job_id: str):
        with self.lock:
            entry = self.active_jobs.get(job_id)
            if entry and entry.state in ("completed", "stopped", "error"):
                del self.active_jobs[job_id]
