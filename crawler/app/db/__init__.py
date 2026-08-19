"""system.db의 단일 MongoClient를 재사용한다 — 예전에는 이 서비스가 자체
MongoClient(+SSH 터널)를 별도로 만들어서 프로세스마다 연결이 중복됐다.

이 서비스는 예전부터 MODE와 무관하게 운영 DB를 그대로 썼는데, 이제는 전 서비스가
그렇게 동작하므로(system/db/__init__.py 참고) 더 이상 이 파일만의 예외가 아니다.
아래에서 DB 이름을 직접 적는 것은 system.db가 노출하지 않는 핸들(homepage_db 등)을
같이 쓰기 때문이다."""

import logging
from datetime import datetime

from system.db import client, discord_notifications_db, user_db

logger = logging.getLogger(__name__)

crawler_db_name = "crawler"

crawler_db = client[crawler_db_name]
homepage_db = client["homepage"]

__all__ = [
    "client",
    "crawler_db",
    "homepage_db",
    "user_db",
    "user_logs_db",
    "discord_notifications_db",
    "load_proxy_list",
    "checkState",
    "get_userinfo",
    "get_admin_discord_ids",
    "add_userlog",
    "recordDB",
]

# 예전에도 이 컬렉션은 crawler 프로세스의 MODE와 무관하게 항상 운영 DB(manager.user-logs)를
# 가리켰다 — 지금은 그 데이터가 systems.user-logs로 이관되었으므로 운영 systems DB를 고정해서 쓴다.
user_logs_db = client["systems"]["user-logs"]


def load_proxy_list():
    return client[crawler_db_name]["ip-list"].find_one({"_id": "proxy_list"})["list"]


def checkState(dbUid: str):
    crawlDbList = client[crawler_db_name]["db-list"]
    targetDB = crawlDbList.find_one({"uid": dbUid})
    if targetDB:
        return targetDB["status"]
    else:
        crawler_db["job-queue"].update_one(
            {"db_uid": dbUid},
            {"$set": {"state": "stopped", "finished_at": datetime.now()}},
        )
        return None


def get_userinfo(requester: str):
    try:
        user = user_db.find_one({"name": requester})
        if user is None:
            return False
        return {
            "Email": user["email"],
            "userUid": user["uid"],
            "discord_id": user.get("discord_id"),
        }
    except Exception as e:
        logger.info(f"DB 유저 정보 가져오기 : {requester}, 에러: {e}")
        return False


def get_admin_discord_ids() -> list:
    try:
        cursor = user_db.find(
            {"role": "admin", "discord_id": {"$exists": True, "$ne": None}},
            {"discord_id": 1},
        )
        return [doc["discord_id"] for doc in cursor if doc.get("discord_id")]
    except Exception as e:
        logger.info(f"관리자 디스코드 ID 조회 실패: {e}")
        return []


def add_userlog(userUid: str, dbname: str):
    from system.logging.user_log import insert_log

    insert_log(
        user_logs_db,
        userUid,
        "crawler.crawl.start",
        "crawler",
        message=f"크롤링 시작: {dbname}",
        target={"type": "crawl_db", "id": dbname},
    )


def recordDB(dbUid: str, status: str):
    crawlDbList = client[crawler_db_name]["db-list"]
    crawlDbList.update_one({"uid": dbUid}, {"$set": {"status": status}})
