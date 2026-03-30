import heapq
import threading
from uuid import uuid4
from datetime import datetime
from typing import Optional
import logging

from app.models.job_model import JobSubmitRequest
from app.services.registry import CrawlerRegistry
from app.services.persistence import JobPersistence
from config import SLEEP_TIME

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

    def stop_job(self, job_id: str) -> bool:
        """실행 중 작업 중단"""
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
        if entry is None:
            return False, "not_found"

        if entry.state == "running":
            return False, "running"

        self.registry.remove_finished(job_id)
        self.persistence.delete(job_id)
        return True, entry.state

    def get_job_status(self, job_id: str) -> Optional[dict]:
        """단일 작업의 상태 조회"""
        entry = self.registry.get_entry(job_id)
        if entry:
            return {
                "job_id": entry.job_id,
                "state": entry.state,
                "started_at": entry.started_at.isoformat() if entry.started_at else None,
                "finished_at": entry.finished_at.isoformat() if entry.finished_at else None,
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
                    "started_at": entry.started_at.isoformat() if entry.started_at else None,
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
            recent.append({
                "job_id": doc["job_id"],
                "state": doc["state"],
                "started_at": doc["started_at"].isoformat() if doc.get("started_at") else None,
                "finished_at": doc["finished_at"].isoformat() if doc.get("finished_at") else None,
                "error_message": doc.get("error_message"),
                **doc.get("request", {}),
            })

        return {"active": active, "queued": queued, "recent": recent}

    def restore_from_db(self) -> dict:
        """서버 재시작 시 MongoDB에서 큐 복원. 복원 결과를 dict로 반환."""
        marked_error = self.persistence.mark_running_as_error("서버 재시작으로 중단됨")

        queued_docs = self.persistence.get_by_state("queued")
        for doc in queued_docs:
            req_dict = doc["request"]
            priority = req_dict.get("priority", 0)
            created = doc.get("created_at", datetime.now()).isoformat()
            heapq.heappush(self.queue, (-priority, created, doc["job_id"], req_dict))

        # max_concurrent만큼 시작
        started = 0
        while self.queue and self.registry.active_count() < self.registry.max_concurrent:
            _, _, jid, req_dict = heapq.heappop(self.queue)
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
            logger.info(f"DB 복원: 에러 처리 {marked_error}건, 대기 복원 {len(queued_docs)}건, 즉시 시작 {started}건")

        return result

    # ── 내부 ──────────────────────────────────────────────────────────

    def _start(self, job_id: str, req: JobSubmitRequest):
        """크롤러 인스턴스 생성 후 registry에 제출"""
        try:
            crawler = self._create_crawler(req)
        except Exception as e:
            logger.exception(f"크롤러 생성 실패: {job_id}")
            self.persistence.update_state(job_id, "error", str(e))
            return

        self.persistence.update_state(job_id, "running")
        self.registry.submit(job_id, crawler, req.model_dump())
        logger.info(f"Job {job_id} started: {req.keyword} ({req.start_day}~{req.end_day})")

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
                speed=SLEEP_TIME,
            )
        # 추후 확장:
        # elif req.crawl_object == 2:
        #     from parsers.naver_blog import NaverBlogCrawler
        #     return NaverBlogCrawler(...)
        raise ValueError(f"지원하지 않는 크롤러 타입: {req.crawl_object}")

    def _on_finished(self, job_id: str):
        """registry 콜백: 작업 완료 → DB 업데이트 + 큐에서 다음 작업 시작"""
        entry = self.registry.get_entry(job_id)
        if entry:
            self.persistence.update_state(job_id, entry.state, entry.error_message)
            logger.info(f"Job {job_id} finished: {entry.state}")

        # 큐에서 다음 작업 시작
        with self.lock:
            if self.queue and self.registry.active_count() < self.registry.max_concurrent:
                _, _, next_id, next_req_dict = heapq.heappop(self.queue)
                next_req = JobSubmitRequest(**next_req_dict)
                self._start(next_id, next_req)
