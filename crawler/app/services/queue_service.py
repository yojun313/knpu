import heapq
import threading
from uuid import uuid4
from datetime import datetime
from typing import Optional
import logging

from app.models.job_model import JobSubmitRequest
from app.services.registry import CrawlerRegistry
from app.services.persistence import JobPersistence
from app.db import recordDB, crawler_db

logger = logging.getLogger(__name__)


class QueueManager:
    """우선순위 큐 + CrawlerRegistry + MongoDB 영속화를 통합 관리한다."""

    def __init__(self, registry: CrawlerRegistry, persistence: JobPersistence):
        self.registry = registry
        self.persistence = persistence
        self.lock = threading.Lock()
        # heapq: (-priority, created_at_str, job_id, request_dict)
        self.queue: list = []

        # registry에서 작업 완료 시 콜백
        self.registry.on_job_finished = self._on_finished

    # ── 외부 API ──────────────────────────────────────────────────────

    def enqueue(self, req: JobSubmitRequest) -> str:
        """작업 제출. 용량 있으면 즉시 실행, 아니면 큐에 대기."""
        job_id = uuid4().hex[:8]
        req_dict = req.model_dump()
        self.persistence.save(job_id, req_dict, "queued")

        with self.lock:
            if self.registry.active_count() < self.registry.max_concurrent:
                self._start(job_id, req)
            else:
                heapq.heappush(
                    self.queue,
                    (-req.priority, datetime.now().isoformat(), job_id, req_dict),
                )
                logger.info(f"Job {job_id} queued (queue size: {len(self.queue)})")

        return job_id

    def enqueue_resume(self, db_uid: str, end_date: str = None) -> str:
        """중단·에러·완료된 작업을 이어받는다. 같은 db_uid(같은 파일/데이터)로 새 job_id를
        발급해 큐에 넣는다 — 용량 있으면 즉시 실행. 완료된 작업은 이미 원래 종료일까지
        다 끝난 상태이므로, 더 늦은 end_date를 반드시 지정해야 확장해서 이어받을 수 있다."""
        doc = crawler_db["db-list"].find_one({"uid": db_uid})
        if not doc:
            raise ValueError(f"크롤링 작업을 찾을 수 없습니다: {db_uid}")
        status = doc.get("status")
        if status not in ("stopped", "error", "completed"):
            raise ValueError("중단·에러·완료된 작업만 이어받기할 수 있습니다")
        if not doc.get("crawlObject"):
            raise ValueError("이어받기를 지원하지 않는 예전 작업입니다")
        if status == "completed" and not end_date:
            raise ValueError(
                "완료된 크롤링을 이어서 하려면 새 종료일을 입력해야 합니다"
            )

        job_id = uuid4().hex[:8]
        resolved_end = end_date or doc.get("endDate")
        meta = {
            "name": doc.get("requester"),
            "crawl_object": doc.get("crawlObject"),
            "option_select": doc.get("crawlOption"),
            "keyword": doc.get("keyword"),
            "start_day": doc.get("startDate"),
            "end_day": resolved_end,
            "priority": 99,  # 이어받기는 대기 없이 우선 실행되도록 최우선순위
            "speed": doc.get("crawlSpeed", 3),
            "resumed_from": db_uid,
            "resume_end_date": end_date,
        }
        self.persistence.save(job_id, meta, "queued")

        with self.lock:
            if self.registry.active_count() < self.registry.max_concurrent:
                self._start_resume(job_id, db_uid, meta)
            else:
                heapq.heappush(
                    self.queue,
                    (-meta["priority"], datetime.now().isoformat(), job_id, meta),
                )
                logger.info(
                    f"Resume job {job_id} queued (queue size: {len(self.queue)})"
                )

        return job_id

    def stop_job(self, job_id: str) -> bool:
        """실행 중 작업 중단"""
        self.persistence.update_state(job_id, "stopped")
        return self.registry.stop(job_id)

    def cancel_job(self, job_id: str) -> bool:
        """큐에서 대기 중인 작업 제거"""
        success, removed_from = self.remove_job(job_id)
        return success and removed_from == "queued"

    def remove_job(self, job_id: str) -> tuple[bool, str]:
        """작업 삭제(queued, completed/stopped/error 가능). running은 삭제 불가."""
        with self.lock:
            for i, item in enumerate(self.queue):
                if item[2] == job_id:
                    self.queue.pop(i)
                    heapq.heapify(self.queue)
                    self.persistence.delete(job_id)
                    return True, "queued"

        entry = self.registry.get_entry(job_id)
        if entry and entry.state == "running":
            return False, "running"

        self.registry.remove_finished(job_id)
        self.persistence.delete(job_id)
        return True, ""

    def get_job_status(self, job_id: str) -> Optional[dict]:
        """단일 작업의 상태 조회"""
        entry = self.registry.get_entry(job_id)
        if entry:
            return {
                "job_id": entry.job_id,
                "state": entry.state,
                "started_at": entry.started_at.isoformat()
                if entry.started_at
                else None,
                "finished_at": entry.finished_at.isoformat()
                if entry.finished_at
                else None,
                "error_message": entry.error_message,
                "crawler_status": self.registry.get_status(job_id),
                **entry.meta,
            }

        # 큐에서 찾기
        with self.lock:
            for item in self.queue:
                if item[2] == job_id:
                    return {"job_id": job_id, "state": "queued", **item[3]}

        return None

    def get_all_statuses(self) -> dict:
        """대시보드용 전체 상태. active + queued + recent 분류."""
        active = []

        for entry in self.registry.all_entries():
            if entry.state == "running":
                status_data = {
                    "job_id": entry.job_id,
                    "state": entry.state,
                    "started_at": entry.started_at.isoformat()
                    if entry.started_at
                    else None,
                    "crawler_status": self.registry.get_status(entry.job_id),
                    **entry.meta,
                }
                active.append(status_data)

        queued = []
        with self.lock:
            for item in self.queue:
                queued.append({"job_id": item[2], "state": "queued", **item[3]})

        # 최근 7일 완료/에러/중단 작업을 DB에서 조회
        recent = []
        for doc in self.persistence.get_recent_days(days=7):
            recent.append(
                {
                    "job_id": doc["job_id"],
                    "state": doc["state"],
                    "db_uid": doc.get("db_uid"),
                    "started_at": doc["started_at"].isoformat()
                    if doc.get("started_at")
                    else None,
                    "finished_at": doc["finished_at"].isoformat()
                    if doc.get("finished_at")
                    else None,
                    "error_message": doc.get("error_message"),
                    **doc.get("request", {}),
                }
            )

        return {"active": active, "queued": queued, "recent": recent}

    def restore_from_db(self) -> dict:
        """서버 재시작 시 MongoDB에서 큐 복원. 복원 결과를 dict로 반환."""
        marked_error, db_uids = self.persistence.mark_running_as_error(
            "서버 재시작으로 중단됨"
        )

        for db_uid in db_uids:
            recordDB(db_uid, "error")

        queued_docs = self.persistence.get_by_state("queued")
        for doc in queued_docs:
            req_dict = doc["request"]
            priority = req_dict.get("priority", 0)
            created = doc.get("created_at", datetime.now()).isoformat()
            heapq.heappush(self.queue, (-priority, created, doc["job_id"], req_dict))

        # max_concurrent만큼 시작
        started = 0
        while (
            self.queue and self.registry.active_count() < self.registry.max_concurrent
        ):
            _, _, jid, req_dict = heapq.heappop(self.queue)
            if req_dict.get("resumed_from"):
                self._start_resume(jid, req_dict["resumed_from"], req_dict)
            else:
                req = JobSubmitRequest(**req_dict)
                self._start(jid, req)
            started += 1

        needed = marked_error > 0 or len(queued_docs) > 0
        result = {
            "needed": needed,
            "marked_error": marked_error,
            "restored": len(queued_docs),
            "started": started,
        }

        if needed:
            logger.info(
                f"DB 복원: 에러 처리 {marked_error}건, 대기 복원 {len(queued_docs)}건, 즉시 시작 {started}건"
            )

        return result

    # ── 내부 ──────────────────────────────────────────────────────────

    def _start(self, job_id: str, req: JobSubmitRequest):
        """크롤러 인스턴스 생성 후 registry에 제출"""
        try:
            crawler = self._create_crawler(req)
            if hasattr(crawler, "DBuid"):
                db_uid = crawler.DBuid
                self.persistence.link_db_uid(job_id, db_uid)
        except Exception as e:
            logger.exception(f"크롤러 생성 실패: {job_id}")
            self.persistence.update_state(job_id, "error", str(e))
            return

        self.persistence.update_state(job_id, "running")
        self.registry.submit(job_id, crawler, req.model_dump())
        logger.info(
            f"Job {job_id} started: {req.keyword} ({req.start_day}~{req.end_day})"
        )

    def _start_resume(self, job_id: str, db_uid: str, meta: dict):
        """이어받기 크롤러 생성 후 registry에 제출 (일반 _start와 달리 fromResume 경유)"""
        try:
            crawler = self._create_resume_crawler(
                meta.get("crawl_object"), db_uid, meta.get("resume_end_date")
            )
            self.persistence.link_db_uid(job_id, db_uid)
        except Exception as e:
            logger.exception(f"이어받기 크롤러 생성 실패: {job_id} (db_uid={db_uid})")
            self.persistence.update_state(job_id, "error", str(e))
            return

        self.persistence.update_state(job_id, "running")
        self.registry.submit(job_id, crawler, meta)
        logger.info(f"Resume job {job_id} started for db_uid={db_uid}")

    def _create_resume_crawler(
        self, crawl_object: int, db_uid: str, end_date: str = None
    ):
        if crawl_object == 1:
            from parsers.naver_news import NaverNewsCrawler

            return NaverNewsCrawler.fromResume(db_uid, end_date)
        elif crawl_object == 2:
            from parsers.naver_blog import NaverBlogCrawler

            return NaverBlogCrawler.fromResume(db_uid, end_date)
        elif crawl_object == 3:
            from parsers.naver_cafe import NaverCafeCrawler

            return NaverCafeCrawler.fromResume(db_uid, end_date)
        elif crawl_object == 4:
            from parsers.youtube import YouTubeCrawler

            return YouTubeCrawler.fromResume(db_uid, end_date)
        elif crawl_object == 5:
            from parsers.china_daily import ChinaDailyCrawler

            return ChinaDailyCrawler.fromResume(db_uid, end_date)
        elif crawl_object == 6:
            from parsers.china_sina import ChinaSinaCrawler

            return ChinaSinaCrawler.fromResume(db_uid, end_date)
        raise ValueError(f"지원하지 않는 크롤러 타입: {crawl_object}")

    def _create_crawler(self, req: JobSubmitRequest):
        """크롤러 팩토리 — crawl_object에 따라 적절한 클래스 생성"""
        if req.crawl_object == 1:
            from parsers.naver_news import NaverNewsCrawler

            return NaverNewsCrawler(
                requester=req.name,
                keyword=req.keyword,
                startDate=req.start_day,
                endDate=req.end_day,
                option=req.option_select,
                speed=req.speed,
            )
        elif req.crawl_object == 2:
            from parsers.naver_blog import NaverBlogCrawler

            return NaverBlogCrawler(
                requester=req.name,
                keyword=req.keyword,
                startDate=req.start_day,
                endDate=req.end_day,
                option=req.option_select,
                speed=req.speed,
            )
        elif req.crawl_object == 3:
            from parsers.naver_cafe import NaverCafeCrawler

            return NaverCafeCrawler(
                requester=req.name,
                keyword=req.keyword,
                startDate=req.start_day,
                endDate=req.end_day,
                option=req.option_select,
                speed=req.speed,
            )
        elif req.crawl_object == 4:
            from parsers.youtube import YouTubeCrawler

            return YouTubeCrawler(
                requester=req.name,
                keyword=req.keyword,
                startDate=req.start_day,
                endDate=req.end_day,
                option=req.option_select,
                speed=req.speed,
            )
        elif req.crawl_object == 5:
            from parsers.china_daily import ChinaDailyCrawler

            return ChinaDailyCrawler(
                requester=req.name,
                keyword=req.keyword,
                startDate=req.start_day,
                endDate=req.end_day,
                option=req.option_select,
                speed=req.speed,
            )
        elif req.crawl_object == 6:
            from parsers.china_sina import ChinaSinaCrawler

            return ChinaSinaCrawler(
                requester=req.name,
                keyword=req.keyword,
                startDate=req.start_day,
                endDate=req.end_day,
                option=req.option_select,
                speed=req.speed,
            )
        raise ValueError(f"지원하지 않는 크롤러 타입: {req.crawl_object}")

    def _on_finished(self, job_id: str):
        """registry 콜백: 작업 완료 → DB 업데이트 + 큐에서 다음 작업 시작"""
        entry = self.registry.get_entry(job_id)
        if entry:
            self.persistence.update_state(job_id, entry.state, entry.error_message)
            logger.info(f"Job {job_id} finished: {entry.state}")

        # 큐에서 다음 작업 시작
        with self.lock:
            if (
                self.queue
                and self.registry.active_count() < self.registry.max_concurrent
            ):
                _, _, next_id, next_req_dict = heapq.heappop(self.queue)
                if next_req_dict.get("resumed_from"):
                    self._start_resume(
                        next_id, next_req_dict["resumed_from"], next_req_dict
                    )
                else:
                    next_req = JobSubmitRequest(**next_req_dict)
                    self._start(next_id, next_req)
