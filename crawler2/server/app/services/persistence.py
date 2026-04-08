from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# MongoDB 연결은 지연 로딩 — DB 없이도 서버 기동 가능
_collection = None


def _get_collection():
    global _collection
    if _collection is None:
        try:
            from db import client
            _collection = client["crawler"]["job-queue"]
        except Exception as e:
            logger.warning(f"MongoDB 연결 실패, 영속화 비활성화: {e}")
            return None
    return _collection


class JobPersistence:
    """MongoDB crawler.job-queue 컬렉션을 통한 작업 영속화.
    MongoDB가 없으면 no-op으로 동작한다 (in-memory only).
    """

    def save(self, job_id: str, request_dict: dict, state: str = "queued"):
        col = _get_collection()
        if col is None:
            return
        col.insert_one({
            "job_id": job_id,
            "state": state,
            "request": request_dict,
            "created_at": datetime.now(),
            "started_at": None,
            "finished_at": None,
            "error_message": None,
        })

    def update_state(self, job_id: str, state: str, error_message: str = None):
        col = _get_collection()
        if col is None:
            return
        update = {"$set": {"state": state}}
        if state == "running":
            update["$set"]["started_at"] = datetime.now()
        elif state in ("completed", "stopped", "error"):
            update["$set"]["finished_at"] = datetime.now()
        if error_message:
            update["$set"]["error_message"] = error_message
        col.update_one({"job_id": job_id}, update)

    def get_by_state(self, state: str) -> list:
        col = _get_collection()
        if col is None:
            return []
        return list(col.find({"state": state}).sort("created_at", 1))

    def get_all_recent(self, limit: int = 50) -> list:
        col = _get_collection()
        if col is None:
            return []
        return list(col.find().sort("created_at", -1).limit(limit))

    def get_recent_days(self, days: int = 7) -> list:
        """최근 N일 내 완료/에러/중단된 작업 조회"""
        col = _get_collection()
        if col is None:
            return []
        cutoff = datetime.now() - timedelta(days=days)
        return list(col.find({
            "state": {"$in": ["completed", "error", "stopped"]},
            "finished_at": {"$gte": cutoff},
        }).sort("finished_at", -1))

    def mark_running_as_error(self, message: str) -> int:
        col = _get_collection()
        if col is None:
            return 0
        result = col.update_many(
            {"state": "running"},
            {"$set": {"state": "error", "error_message": message, "finished_at": datetime.now()}},
        )
        return result.modified_count

    def delete(self, job_id: str):
        col = _get_collection()
        if col is None:
            return
        col.delete_one({"job_id": job_id})
