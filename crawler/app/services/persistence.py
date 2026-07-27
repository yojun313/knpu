from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

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
    def link_db_uid(self, job_id: str, db_uid: str):
        col = _get_collection()
        if col is not None:
            col.update_one({"job_id": job_id}, {"$set": {"db_uid": db_uid}})

    def save(self, job_id: str, request_dict: dict, state: str = "queued"):
        col = _get_collection()
        if col is None:
            return
        col.insert_one(
            {
                "job_id": job_id,
                "state": state,
                "request": request_dict,
                "created_at": datetime.now(),
                "started_at": None,
                "finished_at": None,
                "error_message": None,
            }
        )

    def update_state(self, job_id: str, state: str, error_message: str = None):
        col = _get_collection()
        if col is None:
            return

        current_job = col.find_one({"job_id": job_id}, {"state": 1, "db_uid": 1})
        if current_job:
            current_state = current_job.get("state")
            if current_state in ("stopped", "error") and state == "completed":
                return

        update = {"$set": {"state": state}}
        if state == "running":
            update["$set"]["started_at"] = datetime.now()
        elif state in ("completed", "stopped", "error"):
            update["$set"]["finished_at"] = datetime.now()
        if error_message:
            update["$set"]["error_message"] = error_message

        col.update_one({"job_id": job_id}, update)

        job_doc = col.find_one({"job_id": job_id})
        if job_doc and "db_uid" in job_doc and state in ["stopped", "error"]:
            self._update_db_list_status(job_doc["db_uid"], state)

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
        col = _get_collection()
        if col is None:
            return []
        cutoff = datetime.now() - timedelta(days=days)
        return list(
            col.find(
                {
                    "state": {"$in": ["completed", "error", "stopped"]},
                    "finished_at": {"$gte": cutoff},
                }
            ).sort("finished_at", -1)
        )

    def mark_running_as_error(self, message: str) -> tuple[int, list[str]]:
        col = _get_collection()
        if col is None:
            return []

        running_docs = col.find({"state": "running"}, {"db_uid": 1})
        db_uids = [doc["db_uid"] for doc in running_docs if "db_uid" in doc]

        result = col.update_many(
            {"state": "running"},
            {
                "$set": {
                    "state": "error",
                    "error_message": message,
                    "finished_at": datetime.now(),
                }
            },
        )

        return result.modified_count, db_uids

    def get_logs(self, job_id: str) -> list:
        col = _get_collection()
        if col is None:
            return []
        job_doc = col.find_one({"job_id": job_id}, {"db_uid": 1})
        if not job_doc or "db_uid" not in job_doc:
            return []
        try:
            from db import client

            log_doc = client["crawler"]["log-list"].find_one({"uid": job_doc["db_uid"]})
            return log_doc.get("logs", []) if log_doc else []
        except Exception as e:
            logger.warning(f"로그 조회 실패 (job_id: {job_id}): {e}")
            return []

    def delete(self, job_id: str):
        col = _get_collection()
        if col is None:
            return
        col.delete_one({"job_id": job_id})

    def _update_db_list_status(self, db_uid: str, state: str):
        try:
            from db import client

            db_list_col = client["crawler"]["db-list"]
            db_list_col.update_one({"uid": db_uid}, {"$set": {"status": state}})
        except Exception as e:
            logger.error(f"db-list 상태 동기화 실패: {e}")
