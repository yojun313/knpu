from pymongo import MongoClient
from dotenv import load_dotenv
import os
import socket
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from config import MODE
import uuid

load_dotenv()

SSH_HOST = os.getenv("SSH_HOST")
SSH_PORT = int(os.getenv("SSH_PORT", 22))
SSH_USER = os.getenv("SSH_USER")
SSH_KEY = os.getenv("SSH_KEY")

# MongoDB 설정
MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_AUTH_DB = os.getenv("MONGO_AUTH_DB", "admin")

hostname = socket.gethostname()
is_server = "knpu" in hostname or "server" in hostname  # 서버 이름 기준으로 판단

logger = logging.getLogger(__name__)

if is_server:
    # 서버 내부에서 실행 → 로컬 MongoDB 바로 사용
    client = MongoClient(
        f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
        f"@localhost:{MONGO_PORT}/?authSource={MONGO_AUTH_DB}"
    )
else:
    import warnings

    warnings.filterwarnings("ignore", module="paramiko")
    from sshtunnel import SSHTunnelForwarder

    # 외부에서 실행 → SSH 터널 사용
    server = SSHTunnelForwarder(
        (SSH_HOST, SSH_PORT),
        ssh_username=SSH_USER,
        ssh_pkey=SSH_KEY,
        remote_bind_address=(MONGO_HOST, MONGO_PORT),
        set_keepalive=30,  # 30초마다 keepalive 패킷 전송 → idle timeout 방지
    )
    server.start()

    client = MongoClient(
        f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
        f"@127.0.0.1:{server.local_bind_port}/?authSource={MONGO_AUTH_DB}"
    )

manager_db_name = "manager"
crawler_db_name = "crawler"
homepage_db_name = "homepage"

crawler_db = client[crawler_db_name]
manager_db = client[manager_db_name]
homepage_db = client[homepage_db_name]

user_db = homepage_db["users"]
user_logs_db = manager_db["user-logs"]

# 디스코드 봇(bot/)이 폴링해서 실제 전송을 처리하는 알림 큐
discord_notifications_db = client["discord"]["notifications"]


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
            "PushOver": user.get("pushover_key"),
            "userUid": user["uid"],
            "discord_id": user.get("discord_id"),
        }
    except Exception as e:
        logger.info(f"DB 유저 정보 가져오기 : {requester}, 에러: {e}")
        return False


def get_admin_discord_ids() -> list:
    """관리자(role: admin) 중 디스코드 계정이 연동된 유저의 discord_id 목록"""
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
    try:
        kst = ZoneInfo("Asia/Seoul")
        now_kst = datetime.now(kst)

        log_entry = {
            "uid": str(uuid.uuid4()),
            "userUid": userUid,
            "datetime": now_kst,
            "datetime_kst": now_kst.strftime("%Y-%m-%d %H:%M:%S"),
            "message": f"CRAWLER -> Started crawling: {dbname}",
        }
        user_logs_db.insert_one(log_entry)
    except Exception as e:
        logger.info(f"DB 유저 로그 추가 실패 : {userUid}, 에러: {e}")


def recordDB(dbUid: str, status: str):
    crawlDbList = client[crawler_db_name]["db-list"]
    crawlDbList.update_one({"uid": dbUid}, {"$set": {"status": status}})
